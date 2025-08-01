#!/usr/bin/env python3
"""
Amazon Bedrock Prompt Management의 prompt 조회
"""

import boto3
import json
from typing import Dict, Optional, Any
from botocore.exceptions import ClientError


# 환경 변수 설정
ENVIRONMENT_CONFIG = {
    'dev': {
        'parameter_store_path': '/prompts/text2sql/dev/current',
        'description': 'Development Environment',
        'default_tags': {
            'Environment': 'DEV',
            'Status': 'TESTING'
        }
    },
    'prod': {
        'parameter_store_path': '/prompts/text2sql/prod/current',
        'description': 'Production Environment',
        'default_tags': {
            'Environment': 'PROD',
            'Status': 'ACTIVE'
        }
    }
}

class PromptUtils:
    def __init__(self, region_name: str = 'us-west-2'):
        self.ssm_client = boto3.client('ssm', region_name=region_name)
        self.bedrock_agent_client = boto3.client('bedrock-agent', region_name=region_name)
        self.region = region_name
    
    def get_prompt_identifier_from_parameter(self, parameter_name: str) -> Optional[str]:
        """Parameter Store에서 Prompt ARN 또는 ID 조회"""
        try:
            response = self.ssm_client.get_parameter(
                Name=parameter_name,
                WithDecryption=True
            )
            prompt_identifier = response['Parameter']['Value']
            print(f"Retrieved Prompt identifier from Parameter Store: {prompt_identifier}")
            return prompt_identifier
        except ClientError as e:
            print(f"Error retrieving parameter {parameter_name}: {e}")
            return None
    
    def get_prompt_content_via_parameter(self, parameter_name: str) -> Optional[Dict[str, Any]]:
        """Parameter Store를 통해 Prompt 내용을 완전히 조회"""
        # 1. Parameter Store에서 Prompt ID 조회
        prompt_identifier = self.get_prompt_identifier_from_parameter(parameter_name)
        if not prompt_identifier:
            return None
        
        # 2. Bedrock에서 Prompt 상세 정보 조회
        try:
            response = self.bedrock_agent_client.get_prompt(
                promptIdentifier=prompt_identifier
            )
            
            # 3. 응답 데이터 정리
            prompt_info = {
                'name': response.get('name'),
                'description': response.get('description'),
                'version': response.get('version'),
                'arn': response.get('arn'),
                'createdAt': response.get('createdAt'),
                'updatedAt': response.get('updatedAt'),
                'variants': []
            }
            
            # 4. Prompt variants에서 실제 텍스트 추출
            for variant in response.get('variants', []):
                variant_info = {
                    'name': variant.get('name'),
                    'template_type': variant.get('templateType'),
                    'content': None
                }
                
                # 템플릿 설정에서 실제 텍스트 추출
                template_config = variant.get('templateConfiguration', {})
                if 'text' in template_config:
                    variant_info['content'] = template_config['text'].get('text')
                
                prompt_info['variants'].append(variant_info)
            
            return prompt_info
            
        except ClientError as e:
            print(f"Error retrieving prompt details: {e}")
            return None
    
    def get_prompt_text_only(self, parameter_name: str) -> str:
        """Prompt 텍스트만 간단히 반환"""
        print("📝 Simple text retrieval:")
        print("-" * 60)

        content = self.get_prompt_content_via_parameter(parameter_name)
        if content and content.get('variants'):
            return content['variants'][0].get('content', '')
        return ''
    
    def compare_prompts(self, param1: str, param2: str):
        """두 Parameter의 Prompt 내용 비교"""
        print("-" * 60)

        content1 = self.get_prompt_content_via_parameter(param1)
        content2 = self.get_prompt_content_via_parameter(param2)
        
        if not content1 or not content2:
            print("❌ One or both prompts could not be retrieved")
            return
        
        text1 = content1['variants'][0].get('content', '') if content1.get('variants') else ''
        text2 = content2['variants'][0].get('content', '') if content2.get('variants') else ''
        
        print("\n")
        print(f"Parameter 1: {param1}")
        print(f"Content: {text1}")
        print(f"\nParameter 2: {param2}")
        print(f"Content: {text2}")
        print(f"\n🔍 Same content: {'✅ Yes' if text1 == text2 else '❌ No'}")
    
    def list_prompt_environments(self, base_path: str):
        """환경별 Prompt Parameter 조회"""
        environments = ['dev', 'prod']
        
        print(f"🌍 2. Environment-based Prompt Status for: {base_path}")
        print("-" * 60)
        
        for env in environments:
            param_name = f"{base_path}/{env}/current"
            content = self.get_prompt_content_via_parameter(param_name)
            
            if content:
                prompt_text = content['variants'][0].get('content', '')[:50] + "..." if content.get('variants') else 'No content'
                print(f"✅ {env.upper():8} | {content.get('name')} | {prompt_text}")
            else:
                print(f"❌ {env.upper():8} | Not found or error")

# 사용 예제
if __name__ == "__main__":
    utils = PromptUtils()
    
    # 1. 간단하게 모든 환경의 프롬프트 텍스트 조회
    print("\n" + "="*60)
    print("📝 1. Retrieving prompts from all environments:")
    print("-" * 60)
    
    for env_name, env_config in ENVIRONMENT_CONFIG.items():
        parameter_path = env_config['parameter_store_path']
        description = env_config['description']
        
        print(f"\n🌍 Environment: {env_name.upper()} ({description})")
        print(f"📍 Parameter Path: {parameter_path}")
        
        text = utils.get_prompt_text_only(parameter_path)
        if text:
            # 텍스트가 너무 길면 처음 100자만 표시
            display_text = text[:100] + "..." if len(text) > 100 else text
            print(f"✅ Prompt text: {display_text}")
        else:
            print("❌ No prompt text found")
        
        print("-" * 40)
    
    print("\n" + "="*60)
    
    # 2. 환경별 상태 조회 (환경 변수 기반)
    print("🌍 2. Environment-based Prompt Status:")
    print("-" * 60)
    
    for env_name, env_config in ENVIRONMENT_CONFIG.items():
        param_name = env_config['parameter_store_path']
        content = utils.get_prompt_content_via_parameter(param_name)
        
        if content:
            prompt_text = content['variants'][0].get('content', '')[:50] + "..." if content.get('variants') else 'No content'
            print(f"✅ {env_name.upper():8} | {content.get('name')} | {prompt_text}")
        else:
            print(f"❌ {env_name.upper():8} | Not found or error")
    
    print("\n" + "="*60)
    
    # 3. 환경별 비교 (환경 변수 기반)
    env_list = list(ENVIRONMENT_CONFIG.items())
    if len(env_list) >= 2:
        env1_name, env1_config = env_list[0]
        env2_name, env2_config = env_list[1]
        
        print(f"📊 3. Prompt Comparing {env1_name.upper()} vs {env2_name.upper()}:")
        utils.compare_prompts(env1_config['parameter_store_path'], env2_config['parameter_store_path'])
    else:
        print("❌ Need at least 2 environments for comparison")

    print("\n" + "="*60)
