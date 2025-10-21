#!/usr/bin/env python3
"""
PDF 파일 처리를 위한 스크립트
"""

import os
import sys
import json
from utils import (
    encode_file, 
    read_html_content, 
    get_file_type,
    create_translation_workflow,
    process_document_with_claude
)
import boto3
from botocore.config import Config

def setup_bedrock_client():
    """Bedrock 클라이언트 설정"""
    region = "us-west-2"
    config = Config(read_timeout=300)
    return boto3.client(service_name="bedrock-runtime", region_name=region, config=config)

def llm_converse_with_file(file_data, html_content, model_id, file_path, file_type, client):
    """Claude 모델에 Converse API를 사용하여 파일(이미지/PDF)과 텍스트를 함께 전송하여 분석 요청"""
    
    # 시스템 프롬프트
    system_prompt = """
    # OCR 텍스트 및 파일 분석을 통한 레이아웃 기반 텍스트 분류 전문가

    ## 역할 정의
    당신은 OCR 텍스트와 원본 파일을 분석하여 번역가가 효율적으로 사용할 수 있도록
    텍스트를 레이아웃 기반으로 분류하는 전문가입니다.

    ## 핵심 임무
    1. 정확성 우선: OCR 오류 및 누락 텍스트 수정
    2. 레이아웃 기반 분류: 시각적 배치에 따른 논리적 그룹핑
    3. 번역 효율성 최적화: 번역가의 작업 흐름 개선

    ## 단계별 분석 프로세스

    ### STEP 1: 오류 수정 및 품질 보증
    <thinking>
    파일과 OCR 텍스트를 비교하여 다음을 수행:
    • 누락된 텍스트 식별 및 추가
    • <td rowspan> 태그가 있는 표 텍스트는 동일 그룹으로 처리
    • 주석이 본문에 섞여있는 경우 분리
    • 문맥상 어색한 부분을 파일 기준으로 수정
    </thinking>

    수정 기준:
    • 파일에서 누락된 텍스트 발견 시 → 해당 그룹에 추가
    • <td rowspan> 태그 텍스트 → 표 내 동일 그룹으로 통합
    • 주석이 본문에 포함된 경우 → 주석 제거 후 정리
    • 문맥상 부자연스러운 문장 → 파일 기준으로 정확한 텍스트 복원

    ### STEP 2: 시각적 레이아웃 분석
    <analysis>
    다음 요소들을 체계적으로 분석:
    1. 공간적 위치 관계 (상하좌우 배치)
    2. 시각적 구분 요소 (폰트 크기, 색상, 스타일)
    3. 구조적 경계선 (박스, 테두리, 구분선)
    4. 계층적 구조 (제목-부제목-본문 관계)
    </analysis>

    ### STEP 3: HTML Figure 요소 특별 처리
    Figure 태그 처리 규칙:
    • <figure> 태그 내용 = 하나의 완전한 논리적 단위
    • <figcaption> + 관련 이미지/차트 = 함께 그룹핑
    • 표, 그래프, 도표의 제목과 데이터 = 연결하여 처리

    ### STEP 4: 그룹핑 전략
    우선순위 기준:
    1. 시각적 근접성 > 의미적 연관성
    2. 동일한 디자인 요소 (배경색, 테두리 등)
    3. 레이아웃상 위치 기반 분류
    4. Figure 요소 별도 그룹 처리

    번역 효율성 고려사항:
    • 번역가의 문맥 이해를 위한 적절한 단위 유지
    • 과도한 세분화 방지
    • 제목/헤더는 독립 그룹으로 처리
    • 의미가 다른 영역은 명확히 분리

    ## 출력 형식

    json
    [
        ["제목 텍스트"],
        ["관련된 본문 텍스트1", "본문 텍스트2"],
        ["figure: 차트 제목", "데이터 항목1", "데이터 항목2", "설명 텍스트"],
        ["다음 섹션 제목"],
        ["해당 섹션 내용1", "내용2"]
    ]

    ## 품질 검증 체크리스트
    • [ ] 모든 OCR 텍스트가 포함되었는가?
    • [ ] 파일에서 누락된 텍스트가 추가되었는가?
    • [ ] 시각적 레이아웃이 논리적으로 반영되었는가?
    • [ ] Figure 요소가 적절히 그룹화되었는가?
    • [ ] 번역가가 문맥을 이해하기 쉬운 단위로 분류되었는가?
    """
    
    # 사용자 프롬프트
    if file_type == 'pdf':
        user_prompt = f"""
다음은 PDF 문서와 OCR로 추출된 HTML 텍스트입니다.

PDF 문서를 직접 분석하고, OCR HTML 텍스트와 비교하여 누락되거나 잘못된 부분을 수정한 후,
번역가가 효율적으로 사용할 수 있도록 레이아웃 기반으로 텍스트를 분류해주세요.

**OCR HTML 텍스트:**
{html_content}

위의 단계별 분석 프로세스를 따라 JSON 배열 형태로 결과를 제공해주세요.
"""
    else:
        user_prompt = f"""
다음은 OCR로 추출된 HTML 텍스트와 원본 이미지입니다.

이미지와 OCR 텍스트를 함께 분석하여 누락되거나 잘못된 부분을 수정한 후,
번역가가 효율적으로 사용할 수 있도록 레이아웃 기반으로 텍스트를 분류해주세요.

**OCR HTML 텍스트:**
{html_content}

위의 단계별 분석 프로세스를 따라 JSON 배열 형태로 결과를 제공해주세요.
"""

    # Converse API 호출
    try:
        if file_type == 'pdf':
            # PDF 처리
            response = client.converse(
                modelId=model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "document": {
                                    "format": "pdf",
                                    "name": "document",  # 확장자 제거
                                    "source": {
                                        "bytes": file_data
                                    }
                                }
                            },
                            {
                                "text": user_prompt
                            }
                        ]
                    }
                ],
                system=[
                    {
                        "text": system_prompt
                    }
                ],
                inferenceConfig={
                    "maxTokens": 4000,
                    "temperature": 0.1
                }
            )
        elif file_type == 'image':
            # 이미지 처리
            from utils import get_image_format
            image_format = get_image_format(file_path)
            
            response = client.converse(
                modelId=model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "image": {
                                    "format": image_format,
                                    "source": {
                                        "bytes": file_data
                                    }
                                }
                            },
                            {
                                "text": user_prompt
                            }
                        ]
                    }
                ],
                system=[
                    {
                        "text": system_prompt
                    }
                ],
                inferenceConfig={
                    "maxTokens": 4000,
                    "temperature": 0.1
                }
            )
        
        # 응답에서 텍스트 추출
        response_text = response['output']['message']['content'][0]['text']
        return response_text
        
    except Exception as e:
        raise Exception(f"Claude 모델 호출 중 오류 발생: {str(e)}")

def main_process_file(file_path, html_path):
    """파일 타입에 관계없이 처리하는 메인 함수"""
    
    print("=== 파일 분석 시작 ===")
    
    try:
        # 클라이언트 설정
        client = setup_bedrock_client()
        model_id = "us.anthropic.claude-sonnet-4-20250514-v1:0"
        
        # 1. 파일 타입 확인 및 인코딩
        file_type = get_file_type(file_path)
        print(f"1. 파일 타입: {file_type}")
        
        if file_type == 'pdf':
            print("   PDF를 인코딩 중...")
            from utils import encode_pdf
            import base64
            file_data = base64.b64decode(encode_pdf(file_path))
        elif file_type == 'image':
            print("   이미지를 인코딩 중...")
            from utils import encode_image
            import base64
            file_data = base64.b64decode(encode_image(file_path))
        else:
            raise ValueError(f"지원하지 않는 파일 형식: {file_type}")
        
        print("   파일 인코딩 완료")
        
        # 2. HTML 내용 읽기
        print("2. OCR 결과를 읽는 중...")
        html_content = read_html_content(html_path)
        print(f"   HTML 내용 길이: {len(html_content)} 문자")
        
        # 3. 모델로 분석 작업
        print("3. LLM 모델로 텍스트 그룹 분석 중...")
        
        claude_response = llm_converse_with_file(
            file_data, html_content, model_id, file_path, file_type, client
        )
        
        print("   Claude 분석 완료")
        
        # 4. JSON 파싱
        print("4. 결과를 파싱 중...")
        
        if not claude_response or claude_response.strip() == "":
            print("   Claude 응답이 비어있습니다.")
            grouped_texts = [{"category": "General", "texts": ["응답 없음"]}]
        else:
            print(f"   Claude 응답 길이: {len(claude_response)} 문자")
            
            try:
                json_text = claude_response.strip()
                
                # 마크다운 JSON 코드 블록 찾기
                if "```json" in claude_response:
                    json_start = claude_response.find("```json") + 7
                    json_end = claude_response.find("```", json_start)
                    
                    if json_end != -1:
                        json_text = claude_response[json_start:json_end].strip()
                    else:
                        json_text = claude_response[json_start:].strip()
                elif "```" in claude_response:
                    json_start = claude_response.find("```") + 3
                    json_end = claude_response.find("```", json_start)
                    
                    if json_end != -1:
                        json_text = claude_response[json_start:json_end].strip()
                    else:
                        json_text = claude_response[json_start:].strip()
                
                print(f"   파싱할 JSON 텍스트: {json_text[:100]}...")
                
                parsed_result = json.loads(json_text)
                
                # 다양한 JSON 구조 처리
                if isinstance(parsed_result, list):
                    grouped_texts = [{"category": f"Group {i+1}", "texts": group} for i, group in enumerate(parsed_result)]
                elif isinstance(parsed_result, dict):
                    if 'groups' in parsed_result:
                        grouped_texts = parsed_result['groups']
                    else:
                        grouped_texts = [{"category": "General", "texts": [str(parsed_result)]}]
                else:
                    grouped_texts = [{"category": "General", "texts": [str(parsed_result)]}]
                
            except json.JSONDecodeError as e:
                print(f"   JSON 파싱 실패: {str(e)}")
                print("   원본 응답을 단순 그룹으로 처리합니다.")
                grouped_texts = [{"category": "General", "texts": [claude_response]}]
        
        print(f"   총 {len(grouped_texts)}개의 텍스트 그룹 생성")
        
        # 5. 번역 문서 생성
        print("5. 번역 문서 생성 중...")
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        final_file_path = create_translation_workflow(
            grouped_texts=grouped_texts,
            document_name=file_name,
            source_lang="Korean",
            target_lang="English"
        )
        
        print("\n=== 전체 프로세스 완료 ===")
        print(f"최종 파일: {final_file_path}")
        
        return final_file_path, grouped_texts
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        return None, None

if __name__ == "__main__":
    # 파일 경로 설정
    file_path = "samples/4.pdf"
    html_path = "ocr-results-with-upstage/4.html"
    
    # 파일 존재 여부 확인
    file_exists = os.path.exists(file_path)
    html_exists = os.path.exists(html_path)
    
    print(f"파일: {file_path} ({'존재' if file_exists else '없음'})")
    print(f"HTML 파일: {html_path} ({'존재' if html_exists else '없음'})")
    
    if file_exists and html_exists:
        print("\n" + "="*50)
        print("프로세스를 시작합니다...")
        print("="*50)
        
        print("\n>>> 전사 작업 실행 중...")
        final_file, groups = main_process_file(file_path, html_path)
        
        if final_file:
            print(f"\n✅ 성공적으로 완료되었습니다!")
            print(f"📁 번역 문서 위치: {final_file}")
            print(f"📊 텍스트 그룹 수: {len(groups) if groups else 0}")
        else:
            print("❌ 프로세스 실행 중 오류가 발생했습니다.")
    else:
        print("❌ 필요한 파일이 없어서 프로세스를 실행할 수 없습니다.")