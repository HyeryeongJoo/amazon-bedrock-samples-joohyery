# Bedrock Translate - 통합 문서 처리 시스템

이 프로젝트는 Amazon Bedrock의 Claude 4 모델을 사용하여 이미지와 PDF 파일에서 텍스트를 추출하고 번역용 엑셀 문서를 생성하는 시스템입니다.

## 주요 기능

### 1. 다중 파일 형식 지원
- **이미지 파일**: JPG, PNG, GIF, BMP, WEBP
- **PDF 파일**: Claude 4의 PDF Chat 기능 활용

### 2. Claude 4 모델 활용
- **Vision 기능**: 이미지에서 텍스트 추출
- **PDF Chat 기능**: PDF 문서에서 텍스트 추출
- **Converse API**: 통합된 멀티모달 처리

### 3. 자동 번역 문서 생성
- 추출된 텍스트를 번역가용 엑셀 파일로 변환
- 구조화된 번역 워크플로우 제공
- 다국어 번역 지원 (기본: 한국어 → 영어)

## 파일 구조

```
bedrock-translate/
├── utils.py                           # 핵심 유틸리티 함수들
├── document-processor.ipynb           # 통합 문서 처리 노트북 (신규)
├── ocr-with-llm.ipynb                # 기존 이미지 OCR 노트북
├── preprocess-with-llm_proposed.ipynb # 기존 전처리 노트북
├── samples/                          # 샘플 파일들
│   ├── *.jpg, *.png                 # 이미지 파일들
│   └── *.pdf                        # PDF 파일들
├── final_results/                    # 생성된 번역 문서들
├── extracted_texts/                  # 추출된 텍스트 파일들
└── processed_images/                 # 전처리된 이미지들
```

## 주요 함수

### PDF 처리 함수들
- `is_pdf()`: PDF 파일 감지
- `encode_pdf()`: PDF를 base64로 인코딩
- `process_pdf_with_claude()`: Claude 4 PDF Chat으로 텍스트 추출

### 이미지 처리 함수들 (기존)
- `is_image()`: 이미지 파일 감지
- `encode_image()`: 이미지를 base64로 인코딩
- `process_image_with_claude()`: Claude 4 Vision으로 텍스트 추출

### 통합 처리 함수들
- `get_file_type()`: 파일 타입 자동 감지
- `process_document_with_claude()`: 파일 타입에 따른 자동 처리
- `create_translation_workflow()`: 번역 문서 생성 워크플로우

## 사용 방법

### 1. 통합 문서 처리 (권장)

새로운 `document-processor.ipynb` 노트북을 사용하세요:

```python
# 파일 경로 설정 (이미지 또는 PDF)
target_file = "samples/sample3.pdf"  # PDF 파일
# target_file = "samples/sample1.jpg"  # 이미지 파일

# 문서 처리 실행
final_file, groups, extracted_text = process_document_for_translation(target_file, client)
```

### 2. 배치 처리

여러 파일을 한 번에 처리:

```python
batch_files = [
    "samples/sample1.jpg",
    "samples/sample3.pdf",
    "samples/6.png"
]

batch_results = batch_process_documents(batch_files, client)
```

### 3. 개별 기능 사용

```python
# 파일 타입 확인
file_type = get_file_type("samples/document.pdf")  # 'pdf', 'image', 'unknown'

# 텍스트 추출
extracted_text = process_document_with_claude("samples/document.pdf", client)

# 번역 문서 생성
final_file = create_translation_workflow(
    grouped_texts=text_groups,
    document_name="document",
    source_lang="Korean",
    target_lang="English"
)
```

## 설정 요구사항

### 1. AWS 설정
```python
region = "us-west-2"
claude4_model_id = "us.anthropic.claude-sonnet-4-20250514-v1:0"

config = Config(read_timeout=300)
client = boto3.client(service_name="bedrock-runtime", region_name=region, config=config)
```

### 2. 필요한 패키지
```bash
pip install boto3 Pillow openpyxl pandas
```

## 출력 결과

### 1. 번역 문서 (Excel)
- 파일 위치: `final_results/translation_document_[파일명]_[타임스탬프].xlsx`
- 구조화된 번역 워크시트
- 원본 텍스트와 번역 텍스트 컬럼
- 상태 추적 및 메모 기능

### 2. 추출된 텍스트 (TXT)
- 파일 위치: `extracted_texts/[파일명]_extracted.txt`
- 원본 추출 텍스트 보관

## 주요 개선사항

### 1. PDF 지원 추가
- Claude 4의 PDF Chat 기능 활용
- 문서 형식 자동 감지
- 통합된 처리 파이프라인

### 2. 코드 구조 개선
- 모듈화된 함수 구조
- 타입 힌트 추가
- 에러 처리 강화

### 3. 사용성 향상
- 통합 노트북 제공
- 배치 처리 지원
- 자동 파일 타입 감지

## 예시 사용 시나리오

1. **마케팅 자료 번역**: PDF 브로셔나 이미지 리플렛에서 텍스트 추출 후 번역
2. **문서 현지화**: 다국어 문서 생성을 위한 텍스트 추출
3. **콘텐츠 관리**: 다양한 형식의 문서에서 일관된 텍스트 추출

이제 이미지와 PDF 파일 모두를 지원하는 통합 문서 처리 시스템을 사용할 수 있습니다!