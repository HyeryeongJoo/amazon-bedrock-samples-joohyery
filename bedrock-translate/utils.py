# utils.py
"""
번역 문서 생성을 위한 유틸리티 함수들
"""

import os
import base64
import io
import pandas as pd
from PIL import Image
from datetime import datetime
from typing import Dict, List, Optional

# =============================================================================
# 이미지 처리 함수들
# =============================================================================

def get_image_format(image_path: str) -> str:
    """이미지 형식 자동 감지"""
    try:
        with Image.open(image_path) as img:
            format_map = {
                'JPEG': 'jpeg',
                'PNG': 'png',
                'GIF': 'gif',
                'BMP': 'bmp',
                'WEBP': 'webp'
            }
            return format_map.get(img.format, 'jpeg')
    except:
        # 기본값으로 jpeg 반환
        return 'jpeg'

def validate_and_resize_image(image_path: str, max_pixel: int = 8000) -> str:
    """이미지 크기 검증 및 필요시 리사이징 (세로, 가로 중 하나라도 max_pixel 초과하지 않도록)"""
    try:
        # 이미지 열기
        with Image.open(image_path) as img:
            width, height = img.size
            print(f"원본 이미지 크기: {width}x{height}")
            
            # 크기 검증
            if height <= max_pixel and width <= max_pixel:
                print("이미지 크기가 적절합니다.")
                # 원본 이미지를 base64로 인코딩
                with open(image_path, 'rb') as image_file:
                    return base64.b64encode(image_file.read()).decode('utf-8')
            
            # 리사이징 필요
            print(f"이미지 크기가 너무 큽니다. 리사이징 중... (최대: {max_pixel}x{max_pixel})")
            
            # 비율 유지하며 리사이징
            ratio = min(max_pixel / width, max_pixel / height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            print(f"리사이징된 이미지 크기: {new_width}x{new_height}")
            
            # 메모리에서 바이트로 변환
            img_buffer = io.BytesIO()
            # 원본 형식 유지 (JPEG, PNG 등)
            format = img.format if img.format else 'JPEG'
            resized_img.save(img_buffer, format=format, quality=95)
            img_buffer.seek(0)
            
            return base64.b64encode(img_buffer.getvalue()).decode('utf-8')
    
    except Exception as e:
        raise Exception(f"이미지 처리 중 오류 발생: {str(e)}")

def encode_image(image_path: str) -> str:
    """이미지를 base64로 인코딩 (크기 검증 포함)"""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_path}")
    
    try:
        # 이미지 크기 검증 및 필요시 리사이징
        return validate_and_resize_image(image_path)
    except Exception as e:
        raise Exception(f"이미지 인코딩 중 오류 발생: {str(e)}")

# =============================================================================
# 파일 처리 함수들
# =============================================================================

def read_html_content(html_path: str) -> str:
    """HTML 파일 내용 읽기"""
    with open(html_path, 'r', encoding='utf-8') as file:
        return file.read()

def add_python_path(module_path):
    """파이썬 경로 추가"""
    import sys
    if os.path.abspath(module_path) not in sys.path:
        sys.path.append(os.path.abspath(module_path))
        print(f"python path: {os.path.abspath(module_path)} is added")
    else:
        print(f"python path: {os.path.abspath(module_path)} already exists")
    print("sys.path: ", sys.path)

# =============================================================================
# 번역 문서 생성 함수들
# =============================================================================

def format_translation_document(grouped_texts: List[Dict], 
                               source_language: str = "Korean", 
                               target_language: str = "English") -> pd.DataFrame:
    """
    번역가가 사용할 엑셀 문서 형식으로 데이터를 포맷팅
    
    Args:
        grouped_texts: Claude가 분석한 텍스트 그룹 리스트
        source_language: 소스 언어 (기본값: Korean)
        target_language: 타겟 언어 (기본값: English)
    
    Returns:
        pd.DataFrame: 엑셀로 저장할 데이터프레임
    """
    
    # 번역 문서용 데이터 구조 생성
    translation_data = []
    
    for i, group in enumerate(grouped_texts, 1):
        # 각 그룹의 텍스트들을 하나의 문자열로 결합
        if isinstance(group, dict):
            # 그룹이 딕셔너리 형태인 경우
            group_text = ""
            if 'category' in group:
                group_text += f"[{group['category']}]\n"
            if 'texts' in group:
                group_text += "\n".join(group['texts'])
            elif 'content' in group:
                group_text += group['content']
            
            category = group.get('category', f'Group_{i}')
            description = group.get('description', '')
            priority = group.get('priority', 'medium')
            location = group.get('location', '')
            
        elif isinstance(group, str):
            # 그룹이 문자열인 경우
            group_text = group
            category = f'Group_{i}'
            description = ''
            priority = 'medium'
            location = ''
        else:
            # 기타 형태인 경우
            group_text = str(group)
            category = f'Group_{i}'
            description = ''
            priority = 'medium'
            location = ''
        
        # 빈 텍스트는 제외
        if group_text.strip():
            translation_data.append({
                'ID': f'T{i:03d}',
                'Category': category,
                'Priority': priority,
                'Location': location,
                'Description': description,
                f'Original_Text_{source_language}': group_text.strip(),
                f'Translated_Text_{target_language}': '',  # 번역가가 채울 빈 칸
                'Notes': '',  # 번역가가 메모할 수 있는 칸
                'Status': 'Pending'  # 번역 상태
            })
    
    # 데이터프레임 생성
    df = pd.DataFrame(translation_data)
    
    return df

def save_translation_document(df: pd.DataFrame, 
                             filename: str = None, 
                             image_name: str = "document") -> str:
    """
    번역 문서를 final_results 폴더에 엑셀 파일로 저장
    
    Args:
        df: 저장할 데이터프레임
        filename: 파일명 (None인 경우 자동 생성)
        image_name: 원본 이미지 이름 (파일명에 포함)
    
    Returns:
        str: 저장된 파일의 전체 경로
    """
    
    # final_results 폴더 생성
    current_dir = os.getcwd()
    final_results_dir = os.path.join(current_dir, 'final_results')
    
    if not os.path.exists(final_results_dir):
        os.makedirs(final_results_dir)
        print(f"'{final_results_dir}' 폴더를 생성했습니다.")
    
    # 파일명 생성
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"translation_document_{image_name}_{timestamp}.xlsx"
    
    # .xlsx 확장자 확인
    if not filename.endswith('.xlsx'):
        filename += '.xlsx'
    
    # 전체 파일 경로
    file_path = os.path.join(final_results_dir, filename)
    
    # 엑셀 파일로 저장 (스타일 적용)
    with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
        # 메인 번역 시트
        df.to_excel(writer, sheet_name='Translation', index=False)
        
        # 워크북과 워크시트 객체 가져오기
        workbook = writer.book
        worksheet = writer.sheets['Translation']
        
        # 스타일 적용
        from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
        
        # 헤더 스타일
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        
        # 테두리 스타일
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # 헤더 행 스타일 적용
        for cell in worksheet[1]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = thin_border
        
        # 데이터 행 스타일 적용
        for row in worksheet.iter_rows(min_row=2, max_row=worksheet.max_row):
            for cell in row:
                cell.border = thin_border
                cell.alignment = Alignment(vertical='top', wrap_text=True)
        
        # 열 너비 자동 조정
        column_widths = {
            'A': 8,   # ID
            'B': 15,  # Category
            'C': 10,  # Priority
            'D': 15,  # Location
            'E': 20,  # Description
            'F': 40,  # Original Text
            'G': 40,  # Translated Text
            'H': 20,  # Notes
            'I': 12   # Status
        }
        
        for col, width in column_widths.items():
            worksheet.column_dimensions[col].width = width
        
        # 행 높이 조정
        for row in range(2, worksheet.max_row + 1):
            worksheet.row_dimensions[row].height = 60
        
        # 정보 시트 추가
        info_data = {
            'Field': ['Creation Date', 'Source Language', 'Target Language', 'Total Groups', 'Instructions'],
            'Value': [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'Korean',
                'English', 
                len(df),
                'Please fill in the Translated_Text column with appropriate translations. Use Notes column for any comments or questions.'
            ]
        }
        info_df = pd.DataFrame(info_data)
        info_df.to_excel(writer, sheet_name='Info', index=False)
    
    print(f"번역 문서가 저장되었습니다: {file_path}")
    print(f"총 {len(df)}개의 텍스트 그룹이 포함되어 있습니다.")
    
    return file_path

def create_translation_workflow(grouped_texts: List[Dict], 
                              image_name: str = "document",
                              source_lang: str = "Korean",
                              target_lang: str = "English") -> str:
    """
    전체 번역 워크플로우 실행
    
    Args:
        grouped_texts: Claude가 분석한 텍스트 그룹들
        image_name: 원본 이미지 이름
        source_lang: 소스 언어
        target_lang: 타겟 언어
    
    Returns:
        str: 저장된 파일 경로
    """
    
    # 1. 번역 문서 포맷팅
    print("번역 문서를 포맷팅 중...")
    translation_df = format_translation_document(
        grouped_texts, 
        source_lang, 
        target_lang
    )
    
    # 2. 문서 저장
    print("번역 문서를 저장 중...")
    file_path = save_translation_document(
        translation_df, 
        image_name=image_name
    )
    
    # 3. 결과 요약 출력
    print("\n=== 번역 문서 생성 완료 ===")
    print(f"파일 경로: {file_path}")
    print(f"텍스트 그룹 수: {len(translation_df)}")
    print(f"소스 언어: {source_lang}")
    print(f"타겟 언어: {target_lang}")
    
    return file_path

# =============================================================================
# 파일 시스템 유틸리티
# =============================================================================

def check_file_paths(image_path: str, html_path: str) -> tuple:
    """파일 경로 존재 여부 확인"""
    image_exists = os.path.exists(image_path)
    html_exists = os.path.exists(html_path)
    
    print(f"이미지 파일: {image_path} ({'존재' if image_exists else '없음'})")
    print(f"HTML 파일: {html_path} ({'존재' if html_exists else '없음'})")
    
    return image_exists, html_exists

def list_ocr_results(base_path: str = None):
    """OCR 결과 폴더의 파일 목록 출력"""
    if base_path is None:
        base_path = os.getcwd()
    
    ocr_results_path = os.path.join(base_path, 'ocr-results')
    
    if os.path.exists(ocr_results_path):
        print("OCR 결과 파일들:")
        for filename in os.listdir(ocr_results_path):
            print(f"  - {filename}")
        return [f for f in os.listdir(ocr_results_path)]
    else:
        print("'ocr-results' 폴더가 현재 위치에 없습니다.")
        return []
