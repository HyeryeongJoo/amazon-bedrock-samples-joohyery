def main_process_converse(image_path, html_path):
    """전체 프로세스를 실행하는 메인 함수 """
    
    print("=== OCR 텍스트와 이미지 분석 시작 ===")
    
    try:
        # 1. 이미지 인코딩
        print("1. 이미지를 인코딩 중...")
        image_base64 = encode_image(image_path)
        print("   이미지 인코딩 완료")
        
        # 2. HTML 내용 읽기
        print("2. OCR 결과를 읽는 중...")
        html_content = read_html_content(html_path)
        print(f"   HTML 내용 길이: {len(html_content)} 문자")
        
        # 3. 모델로 전사 작업
        print("3. LLM 모델로 텍스트 그룹 분석 중...")
        
        claude_response = llm_converse(image_base64, html_content, claude3_7_model_id)
        
        print("   Claude 분석 완료")
        
        # 4. JSON 파싱 (수정된 버전)
        print("4. 결과를 파싱 중...")
        
        # Claude 응답이 비어있는지 확인
        if not claude_response or claude_response.strip() == "":
            print("   Claude 응답이 비어있습니다.")
            grouped_texts = [{"category": "General", "texts": ["응답 없음"]}]
        else:
            print(f"   Claude 응답 길이: {len(claude_response)} 문자")
            
            try:
                json_text = claude_response.strip()
                
                # 마크다운 JSON 코드 블록 찾기 (수정된 로직)
                if "```json" in claude_response:
                    json_start = claude_response.find("```json") + 7  # "```json" 다음부터
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
        image_name = os.path.splitext(os.path.basename(image_path))[0]
        final_file_path = create_translation_workflow(
            grouped_texts=grouped_texts,
            image_name=image_name,
            source_lang="Korean",
            target_lang="English"
        )
        
        print("\\n=== 전체 프로세스 완료 ===")
        print(f"최종 파일: {final_file_path}")
        
        return final_file_path, grouped_texts
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        return None, None