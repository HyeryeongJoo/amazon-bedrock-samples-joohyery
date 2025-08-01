#!/usr/bin/env python3
"""
AWS Bedrock Prompt 태그 기반 버전 제어 및 롤백 데모
환경 변수 설정과 사용자 환경 선택 기능 포함
"""

import boto3
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
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

# 기본 설정
DEFAULT_REGION = 'us-west-2'
SUPPORTED_ENVIRONMENTS = ['dev', 'prod']

class PromptVersionController:
    def __init__(self, region_name: str = DEFAULT_REGION, environment: str = 'dev'):
        self.bedrock_agent = boto3.client('bedrock-agent', region_name=region_name)
        self.ssm_client = boto3.client('ssm', region_name=region_name)
        self.region = region_name
        self.environment = environment.lower()
        
        # 환경 설정 검증
        if self.environment not in SUPPORTED_ENVIRONMENTS:
            raise ValueError(f"Unsupported environment: {environment}. Supported: {SUPPORTED_ENVIRONMENTS}")
        
        self.env_config = ENVIRONMENT_CONFIG[self.environment]
        self.parameter_store_path = self.env_config['parameter_store_path']
        
        print(f"🎯 Initialized for {self.env_config['description']}")
        print(f"📍 Parameter Store: {self.parameter_store_path}")
    
    def get_prompt_id_from_environment(self) -> Optional[str]:
        """
        현재 환경의 Parameter Store에서 Prompt ID 조회
        
        Returns:
            Prompt ID 또는 None
        """
        try:
            response = self.ssm_client.get_parameter(
                Name=self.parameter_store_path,
                WithDecryption=True
            )
            prompt_id = response['Parameter']['Value']
            print(f"✅ Retrieved Prompt ID from {self.environment.upper()}: {prompt_id}")
            return prompt_id
        except ClientError as e:
            print(f"❌ Error retrieving parameter {self.parameter_store_path}: {e}")
            return None
    
    def create_tagged_version(self, prompt_identifier: str, content: str, 
                            environment: str = None, version_tag: str = None, description: str = None) -> Optional[str]:
        """
        태그가 포함된 새 버전 생성
        
        Args:
            prompt_identifier: Prompt ID
            content: 새로운 내용
            environment: 환경 (기본값: 현재 환경)
            version_tag: 버전 태그 (v1.0.0, v1.1.0-beta 등)
            description: 버전 설명
            
        Returns:
            새 버전 번호 또는 None
        """
        # 환경 기본값 설정
        if environment is None:
            environment = self.environment
        
        # 버전 태그 기본값 설정
        if version_tag is None:
            timestamp = datetime.now().strftime('%Y%m%d-%H%M')
            version_tag = f"v1.0.0-{environment}-{timestamp}"
        
        try:
            # 1. 먼저 현재 DRAFT 내용 업데이트
            current_prompt = self.bedrock_agent.get_prompt(promptIdentifier=prompt_identifier)
            
            # 기존 variants 복사 및 수정
            updated_variants = []
            for variant in current_prompt.get('variants', []):
                updated_variant = variant.copy()
                updated_variant['templateConfiguration']['text']['text'] = content
                updated_variants.append(updated_variant)
            
            # DRAFT 업데이트
            self.bedrock_agent.update_prompt(
                promptIdentifier=prompt_identifier,
                name=current_prompt.get('name'),
                description=description or current_prompt.get('description'),
                variants=updated_variants
            )
            
            # 2. 새 버전 생성
            version_response = self.bedrock_agent.create_prompt_version(
                promptIdentifier=prompt_identifier,
                description=f"{environment.upper()} {version_tag}: {description or 'Version created'}"
            )
            
            new_version = version_response.get('version')
            new_arn = version_response.get('arn')
            
            # 3. 환경별 기본 태그 + 추가 태그 적용
            base_tags = ENVIRONMENT_CONFIG.get(environment, {}).get('default_tags', {})
            tags = {
                **base_tags,
                'Version': version_tag,
                'CreatedDate': datetime.now().strftime('%Y-%m-%d'),
                'CreatedTime': datetime.now().strftime('%H:%M:%S'),
                'SourceEnvironment': self.environment.upper()
            }
            
            self.bedrock_agent.tag_resource(
                resourceArn=new_arn,
                tags=tags
            )
            
            print(f"✅ Created version {new_version} with tags:")
            for key, value in tags.items():
                print(f"   {key}: {value}")
            
            return new_version
            
        except ClientError as e:
            print(f"❌ Error creating tagged version: {e}")
            return None
    
    def list_versions_with_tags(self, prompt_identifier: str) -> List[Dict]:
        """
        Prompt의 모든 버전과 태그 조회
        
        Args:
            prompt_identifier: Prompt ID
            
        Returns:
            버전 정보 리스트
        """
        try:
            # 모든 버전 조회
            versions = []
            
            # DRAFT 버전
            draft_prompt = self.bedrock_agent.get_prompt(promptIdentifier=prompt_identifier)
            base_arn = draft_prompt.get('arn')
            
            versions.append({
                'version': 'DRAFT',
                'arn': base_arn,
                'name': draft_prompt.get('name'),
                'content': draft_prompt['variants'][0]['templateConfiguration']['text']['text'][:100] + "...",
                'tags': {}  # DRAFT는 태그 없음
            })
            
            # 번호가 있는 버전들 - ARN 형식 사용
            version_num = 1
            max_attempts = 20  # 최대 20개 버전까지 확인
            
            while version_num <= max_attempts:
                try:
                    # ARN 형식으로 버전 조회
                    version_arn = f"{base_arn}:{version_num}"
                    versioned_prompt = self.bedrock_agent.get_prompt(promptIdentifier=version_arn)
                    
                    # 태그 조회
                    try:
                        tags_response = self.bedrock_agent.list_tags_for_resource(
                            resourceArn=version_arn
                        )
                        tags = tags_response.get('tags', {})
                    except:
                        tags = {}
                    
                    versions.append({
                        'version': str(version_num),
                        'arn': version_arn,
                        'name': versioned_prompt.get('name'),
                        'content': versioned_prompt['variants'][0]['templateConfiguration']['text']['text'][:100] + "...",
                        'tags': tags
                    })
                    
                    version_num += 1
                    
                except ClientError as e:
                    if 'ResourceNotFoundException' in str(e) or 'ValidationException' in str(e):
                        # 해당 버전이 없으면 다음 버전 확인
                        version_num += 1
                        continue
                    else:
                        version_num += 1
                        continue
            
            return versions
            
        except ClientError as e:
            print(f"❌ Error listing versions: {e}")
            return []
    
    def rollback_to_version(self, prompt_identifier: str, target_version: str, 
                          rollback_reason: str = "Manual rollback") -> bool:
        """
        특정 버전으로 롤백
        
        Args:
            prompt_identifier: Prompt ID
            target_version: 롤백할 버전 번호
            rollback_reason: 롤백 사유
            
        Returns:
            성공 여부
        """
        try:
            # 1. 현재 DRAFT 정보 조회 (base ARN 얻기 위해)
            current_prompt = self.bedrock_agent.get_prompt(promptIdentifier=prompt_identifier)
            base_arn = current_prompt.get('arn')
            
            # 2. 타겟 버전의 내용 조회
            if target_version == 'DRAFT':
                target_prompt = current_prompt
            else:
                target_arn = f"{base_arn}:{target_version}"
                target_prompt = self.bedrock_agent.get_prompt(promptIdentifier=target_arn)
            
            target_content = target_prompt['variants'][0]['templateConfiguration']['text']['text']
            
            # 3. 현재 DRAFT를 타겟 버전 내용으로 업데이트
            updated_variants = []
            for variant in current_prompt.get('variants', []):
                updated_variant = variant.copy()
                updated_variant['templateConfiguration']['text']['text'] = target_content
                updated_variants.append(updated_variant)
            
            self.bedrock_agent.update_prompt(
                promptIdentifier=prompt_identifier,
                name=current_prompt.get('name'),
                description=f"Rollback to version {target_version}: {rollback_reason}",
                variants=updated_variants
            )
            
            # 4. 롤백 버전 생성 (선택사항)
            rollback_version = self.bedrock_agent.create_prompt_version(
                promptIdentifier=prompt_identifier,
                description=f"ROLLBACK to v{target_version} - {rollback_reason}"
            )
            
            # 5. 롤백 태그 적용
            rollback_arn = rollback_version.get('arn')
            rollback_tags = {
                'Environment': 'ROLLBACK',
                'RollbackFrom': 'DRAFT',
                'RollbackTo': target_version,
                'RollbackDate': datetime.now().strftime('%Y-%m-%d'),
                'RollbackReason': rollback_reason,
                'Status': 'ROLLBACK_COMPLETE',
                'SourceEnvironment': self.environment.upper()
            }
            
            self.bedrock_agent.tag_resource(
                resourceArn=rollback_arn,
                tags=rollback_tags
            )
            
            print(f"✅ Successfully rolled back to version {target_version}")
            print(f"   New rollback version: {rollback_version.get('version')}")
            print(f"   Reason: {rollback_reason}")
            
            return True
            
        except ClientError as e:
            print(f"❌ Error during rollback: {e}")
            return False
    
    def promote_version(self, prompt_identifier: str, from_env: str, to_env: str, 
                       version_tag: str) -> bool:
        """
        환경 간 버전 승격 - 실제 타겟 환경의 Prompt 업데이트
        
        Args:
            prompt_identifier: 소스 환경의 Prompt ID
            from_env: 소스 환경
            to_env: 타겟 환경
            version_tag: 새 버전 태그
            
        Returns:
            성공 여부
        """
        try:
            print(f"🔄 Starting promotion from {from_env.upper()} to {to_env.upper()}...")
            
            # 1. 소스 환경의 현재 DRAFT 내용 가져오기
            source_prompt = self.bedrock_agent.get_prompt(promptIdentifier=prompt_identifier)
            source_content = source_prompt['variants'][0]['templateConfiguration']['text']['text']
            
            print(f"📋 Source content: {source_content[:100]}...")
            
            # 2. 타겟 환경의 Parameter Store에서 Prompt ID 가져오기
            target_param_path = ENVIRONMENT_CONFIG[to_env]['parameter_store_path']
            
            try:
                target_response = self.ssm_client.get_parameter(
                    Name=target_param_path,
                    WithDecryption=True
                )
                target_prompt_id = target_response['Parameter']['Value']
                print(f"🎯 Target Prompt ID ({to_env.upper()}): {target_prompt_id}")
            except ClientError as e:
                print(f"❌ Could not get target environment Prompt ID: {e}")
                return False
            
            # 3. 타겟 환경의 현재 Prompt 정보 가져오기
            try:
                target_prompt = self.bedrock_agent.get_prompt(promptIdentifier=target_prompt_id)
                print(f"📋 Current target content: {target_prompt['variants'][0]['templateConfiguration']['text']['text'][:100]}...")
            except ClientError as e:
                print(f"❌ Could not get target prompt details: {e}")
                return False
            
            # 4. 타겟 환경의 DRAFT를 소스 내용으로 업데이트
            updated_variants = []
            for variant in target_prompt.get('variants', []):
                updated_variant = variant.copy()
                updated_variant['templateConfiguration']['text']['text'] = source_content
                updated_variants.append(updated_variant)
            
            self.bedrock_agent.update_prompt(
                promptIdentifier=target_prompt_id,
                name=target_prompt.get('name'),
                description=f"Promoted from {from_env.upper()} - {version_tag}",
                variants=updated_variants
            )
            
            print(f"✅ Updated {to_env.upper()} DRAFT with {from_env.upper()} content")
            
            # 5. 타겟 환경에서 새 버전 생성
            version_response = self.bedrock_agent.create_prompt_version(
                promptIdentifier=target_prompt_id,
                description=f"Promoted from {from_env.upper()} to {to_env.upper()} - {version_tag}"
            )
            
            new_version = version_response.get('version')
            new_arn = version_response.get('arn')
            
            # 6. 승격 태그 적용
            base_tags = ENVIRONMENT_CONFIG.get(to_env, {}).get('default_tags', {})
            promotion_tags = {
                **base_tags,
                'Version': version_tag,
                'PromotedFrom': from_env.upper(),
                'PromotedDate': datetime.now().strftime('%Y-%m-%d'),
                'PromotedTime': datetime.now().strftime('%H:%M:%S'),
                'SourcePromptId': prompt_identifier,
                'PromotionType': 'ENVIRONMENT_PROMOTION'
            }
            
            self.bedrock_agent.tag_resource(
                resourceArn=new_arn,
                tags=promotion_tags
            )
            
            print(f"✅ Successfully promoted from {from_env.upper()} to {to_env.upper()}")
            print(f"   Source Prompt ID: {prompt_identifier}")
            print(f"   Target Prompt ID: {target_prompt_id}")
            print(f"   New version in {to_env.upper()}: {new_version} ({version_tag})")
            print(f"   Applied tags: {promotion_tags}")
            
            # 7. 승격 후 검증
            verification_prompt = self.bedrock_agent.get_prompt(promptIdentifier=target_prompt_id)
            verification_content = verification_prompt['variants'][0]['templateConfiguration']['text']['text']
            
            if verification_content == source_content:
                print(f"✅ Verification successful: Content matches in {to_env.upper()}")
                return True
            else:
                print(f"⚠️ Verification warning: Content may not match exactly")
                return True
            
        except Exception as e:
            print(f"❌ Error during promotion: {e}")
            import traceback
            traceback.print_exc()
            return False

def interactive_demo():
    """대화형 데모 실행"""
    print("🌍 Environment Selection")
    print("=" * 40)
    print("Available environments:")
    for env in SUPPORTED_ENVIRONMENTS:
        config = ENVIRONMENT_CONFIG[env]
        print(f"  {env.upper()}: {config['description']}")
        print(f"    Parameter Store: {config['parameter_store_path']}")
    
    # 환경 선택
    while True:
        selected_env = input(f"\n👉 Select environment ({'/'.join(SUPPORTED_ENVIRONMENTS)}): ").lower().strip()
        if selected_env in SUPPORTED_ENVIRONMENTS:
            break
        print(f"❌ Invalid environment. Please choose from: {', '.join(SUPPORTED_ENVIRONMENTS)}")
    
    # 선택된 환경으로 컨트롤러 초기화
    controller = PromptVersionController(environment=selected_env)
    
    # 환경에서 Prompt ID 가져오기
    prompt_id = controller.get_prompt_id_from_environment()
    if not prompt_id:
        print("❌ Could not retrieve prompt ID from Parameter Store")
        manual_input = input("Enter Prompt ID manually (or press Enter to exit): ").strip()
        if not manual_input:
            return
        prompt_id = manual_input
    
    print(f"\n🎯 Using Prompt ID: {prompt_id}")
    print(f"🌍 Working in {selected_env.upper()} environment")
    
    while True:
        print("\n" + "="*60)
        print(f"🏷️  Bedrock Prompt Version Control & Rollback Demo ({selected_env.upper()})")
        print("="*60)
        print("1. 📋 List all versions with tags")
        print("2. 🏷️  Create new tagged version")
        print("3. 🔄 Rollback to specific version")
        print("4. 🚀 Promote version between environments")
        print("5. 🔄 Switch environment")
        print("6. 🚪 Exit")
        
        choice = input("\n👉 Select option (1-6): ")
        
        if choice == "1":
            print(f"\n📋 Listing all versions for {selected_env.upper()}...")
            versions = controller.list_versions_with_tags(prompt_id)
            
            print(f"\n📊 Found {len(versions)} versions:")
            for version_info in versions:
                print(f"\n🔖 Version: {version_info['version']}")
                print(f"   Content: {version_info['content']}")
                if version_info['tags']:
                    env = version_info['tags'].get('Environment', 'N/A')
                    ver = version_info['tags'].get('Version', 'N/A')
                    status = version_info['tags'].get('Status', 'N/A')
                    source = version_info['tags'].get('SourceEnvironment', 'N/A')
                    print(f"   🏷️  {env} | {ver} | {status} | Source: {source}")
                else:
                    print('   🏷️  DRAFT | No tags')
        
        elif choice == "2":
            print(f"\n🏷️ Creating new tagged version in {selected_env.upper()}...")
            content = input("Enter new content: ")
            
            # 환경별 기본값 제공
            default_version = f"v1.0.0-{selected_env}"
            version_tag = input(f"Enter version tag (default: {default_version}): ").strip()
            if not version_tag:
                version_tag = default_version
                
            description = input("Enter description (optional): ")
            
            new_version = controller.create_tagged_version(
                prompt_id, content, version_tag=version_tag, description=description
            )
            
            if new_version:
                print(f"✅ Created version {new_version} successfully!")
        
        elif choice == "3":
            print(f"\n🔄 Rolling back in {selected_env.upper()} environment...")
            
            # 먼저 버전 목록 표시
            versions = controller.list_versions_with_tags(prompt_id)
            print("\nAvailable versions:")
            for i, version_info in enumerate(versions):
                env_tag = version_info['tags'].get('Environment', 'N/A')
                ver_tag = version_info['tags'].get('Version', 'N/A')
                print(f"  {i+1}. Version {version_info['version']} - {env_tag} {ver_tag}")
            
            target_version = input("\nEnter version number to rollback to: ")
            reason = input("Enter rollback reason: ")
            
            success = controller.rollback_to_version(prompt_id, target_version, reason)
            if success:
                print("✅ Rollback completed successfully!")
        
        elif choice == "4":
            print(f"\n🚀 Promoting version from {selected_env.upper()}...")
            
            # 타겟 환경 선택
            other_envs = [env for env in SUPPORTED_ENVIRONMENTS if env != selected_env]
            print(f"Available target environments: {', '.join(other_envs)}")
            
            to_env = input(f"To environment ({'/'.join(other_envs)}): ").lower().strip()
            if to_env not in other_envs:
                print("❌ Invalid target environment")
                continue
                
            version_tag = input("New version tag (e.g., v1.3.0): ")
            
            success = controller.promote_version(prompt_id, selected_env, to_env, version_tag)
            if success:
                print("✅ Promotion completed successfully!")
        
        elif choice == "5":
            print("\n🔄 Switching environment...")
            # 재귀 호출로 환경 재선택
            interactive_demo()
            return
        
        elif choice == "6":
            print("👋 Goodbye!")
            break
        
        else:
            print("⚠️ Invalid option, please try again")

def main():
    """메인 실행 함수"""
    print("🚀 Starting Prompt Version Control")
    print("This demo will show you how to:")
    print("  • Select working environment (DEV/PROD)")
    print("  • Create tagged versions")
    print("  • List versions with tags")
    print("  • Rollback to previous versions")
    print("  • Promote between environments")
    
    try:
        interactive_demo()
    except KeyboardInterrupt:
        print("\n\n👋 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")

if __name__ == "__main__":
    main()
