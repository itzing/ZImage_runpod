import runpod
from runpod.serverless.utils import rp_upload
import os
import websocket
import base64
import json
import uuid
import logging
import urllib.request
import urllib.parse
import binascii # Base64 에러 처리를 위해 import
import subprocess
import time
import shutil
import boto3
from botocore.exceptions import NoCredentialsError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


server_address = os.getenv('SERVER_ADDRESS', '127.0.0.1')
client_id = str(uuid.uuid4())


def mask_job_input_for_log(job_input):
    masked = dict(job_input)

    if 'prompt' in masked:
        masked['prompt'] = '[REDACTED]'
    if 'negative_prompt' in masked:
        masked['negative_prompt'] = '[REDACTED]'
    if 'negativePrompt' in masked:
        masked['negativePrompt'] = '[REDACTED]'

    if '_secure' in masked:
        masked['_secure'] = {
            'v': masked.get('_secure', {}).get('v'),
            'alg': masked.get('_secure', {}).get('alg'),
            'kid': masked.get('_secure', {}).get('kid'),
            'ts': masked.get('_secure', {}).get('ts'),
            'nonce': '[REDACTED]',
            'ciphertext': '[REDACTED]'
        }

    if 'lora' in masked:
        masked['lora'] = '[REDACTED]'

    return masked


def decode_encryption_key():
    key_b64 = os.getenv('ZIMAGE_FIELD_ENC_KEY_B64') or os.getenv('FIELD_ENC_KEY_B64')
    if not key_b64:
        return None

    try:
        key = base64.b64decode(key_b64)
    except Exception as error:
        raise Exception(f"Invalid encryption key encoding: {error}")

    if len(key) != 32:
        raise Exception(f"Invalid encryption key length: expected 32 bytes, got {len(key)}")

    return key


def decrypt_secure_input(job_input):
    secure = job_input.get('_secure')
    if not secure:
        return job_input

    key = decode_encryption_key()
    if not key:
        raise Exception("Secure payload received but FIELD_ENC_KEY_B64 is missing")

    try:
        nonce = base64.b64decode(secure['nonce'])
        ciphertext = base64.b64decode(secure['ciphertext'])
        aad = b'engui:zimage:v1'
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
        payload = json.loads(plaintext.decode('utf-8'))
    except Exception as error:
        raise Exception(f"Failed to decrypt secure payload: {error}")

    if 'prompt' in payload:
        job_input['prompt'] = payload.get('prompt', '')

    if 'negative_prompt' in payload:
        job_input['negative_prompt'] = payload.get('negative_prompt', '')
        job_input['negativePrompt'] = payload.get('negative_prompt', '')

    if 'lora_names' in payload:
        names = payload.get('lora_names') or []
        weights = job_input.get('lora_weights') or []
        lora = []

        for index, name in enumerate(names):
            weight = 1.0
            if isinstance(weights, list) and index < len(weights):
                try:
                    weight = float(weights[index])
                except Exception:
                    weight = 1.0

            if name:
                lora.append([name, weight])

        if lora:
            job_input['lora'] = lora

    # Prevent accidental leakage in downstream logs/processing
    job_input.pop('_secure', None)

    return job_input


def to_nearest_multiple_of_16(value):
    """주어진 값을 가장 가까운 16의 배수로 보정, 최소 16 보장"""
    try:
        numeric_value = float(value)
    except Exception:
        raise Exception(f"width/height 값이 숫자가 아닙니다: {value}")
    adjusted = int(round(numeric_value / 16.0) * 16)
    if adjusted < 16:
        adjusted = 16
    return adjusted

def process_input(input_data, temp_dir, output_filename, input_type):
    """입력 데이터를 처리하여 파일 경로를 반환하는 함수"""
    if input_type == "path":
        # 경로인 경우 그대로 반환
        logger.info(f"📁 경로 입력 처리: {input_data}")
        return input_data
    elif input_type == "url":
        # URL인 경우 다운로드
        logger.info(f"🌐 URL 입력 처리: {input_data}")
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.abspath(os.path.join(temp_dir, output_filename))
        return download_file_from_url(input_data, file_path)
    elif input_type == "base64":
        # Base64인 경우 디코딩하여 저장
        logger.info(f"🔢 Base64 입력 처리")
        return save_base64_to_file(input_data, temp_dir, output_filename)
    else:
        raise Exception(f"지원하지 않는 입력 타입: {input_type}")

        
def download_file_from_url(url, output_path):
    """URL에서 파일을 다운로드하는 함수"""
    try:
        # wget을 사용하여 파일 다운로드
        result = subprocess.run([
            'wget', '-O', output_path, '--no-verbose', url
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"✅ URL에서 파일을 성공적으로 다운로드했습니다: {url} -> {output_path}")
            return output_path
        else:
            logger.error(f"❌ wget 다운로드 실패: {result.stderr}")
            raise Exception(f"URL 다운로드 실패: {result.stderr}")
    except subprocess.TimeoutExpired:
        logger.error("❌ 다운로드 시간 초과")
        raise Exception("다운로드 시간 초과")
    except Exception as e:
        logger.error(f"❌ 다운로드 중 오류 발생: {e}")
        raise Exception(f"다운로드 중 오류 발생: {e}")


def save_base64_to_file(base64_data, temp_dir, output_filename):
    """Base64 데이터를 파일로 저장하는 함수"""
    try:
        # Base64 문자열 디코딩
        decoded_data = base64.b64decode(base64_data)
        
        # 디렉토리가 존재하지 않으면 생성
        os.makedirs(temp_dir, exist_ok=True)
        
        # 파일로 저장
        file_path = os.path.abspath(os.path.join(temp_dir, output_filename))
        with open(file_path, 'wb') as f:
            f.write(decoded_data)
        
        logger.info(f"✅ Base64 입력을 '{file_path}' 파일로 저장했습니다.")
        return file_path
    except (binascii.Error, ValueError) as e:
        logger.error(f"❌ Base64 디코딩 실패: {e}")
        raise Exception(f"Base64 디코딩 실패: {e}")
    
def upload_to_r2(image_data, file_name):
    """
    이미지 데이터를 Cloudflare R2에 업로드하고 URL을 반환합니다.
    환경변수 R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME이 필요합니다.
    """
    try:
        account_id = os.environ.get('R2_ACCOUNT_ID')
        access_key = os.environ.get('R2_ACCESS_KEY_ID')
        secret_key = os.environ.get('R2_SECRET_ACCESS_KEY')
        bucket_name = os.environ.get('R2_BUCKET_NAME')
        custom_domain = os.environ.get('R2_CUSTOM_DOMAIN')

        if not all([account_id, access_key, secret_key, bucket_name]):
            logger.error("R2 업로드를 위한 환경변수가 설정되지 않았습니다.")
            return None

        s3_client = boto3.client(
            's3',
            endpoint_url=f'https://{account_id}.r2.cloudflarestorage.com',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )

        # Base64 디코딩
        if isinstance(image_data, str):
            try:
                image_bytes = base64.b64decode(image_data)
            except binascii.Error:
                image_bytes = image_data.encode('utf-8')
        else:
            image_bytes = image_data

        s3_client.put_object(
            Bucket=bucket_name,
            Key=file_name,
            Body=image_bytes,
            ContentType='image/png'
        )
        
        if custom_domain:
            url = f"{custom_domain}/{file_name}"
            # http/https prefix check
            if not url.startswith("http"):
                 url = f"https://{url}"
            logger.info(f"✅ R2 업로드 성공 (Public URL): {url}")
            return url
        else:
            # Custom Domain이 없는 경우 Presigned URL 생성 (1시간 유효)
            try:
                url = s3_client.generate_presigned_url(
                    ClientMethod='get_object',
                    Params={'Bucket': bucket_name, 'Key': file_name},
                    ExpiresIn=3600
                )
                logger.info(f"✅ R2 업로드 성공 (Presigned URL): {url}")
                return url
            except Exception as e:
                logger.error(f"❌ Presigned URL 생성 실패: {e}")
                return None

    except Exception as e:
        logger.error(f"❌ R2 업로드 중 오류 발생: {e}")
        return None

def queue_prompt(prompt):
    url = f"http://{server_address}:8188/prompt"
    logger.info(f"Queueing prompt to: {url}")
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req = urllib.request.Request(url, data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_image(filename, subfolder, folder_type):
    url = f"http://{server_address}:8188/view"
    logger.info(f"Getting image from: {url}")
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen(f"{url}?{url_values}") as response:
        return response.read()

def get_history(prompt_id):
    url = f"http://{server_address}:8188/history/{prompt_id}"
    logger.info(f"Getting history from: {url}")
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())

def get_images(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break
        else:
            continue

    history = get_history(prompt_id)[prompt_id]
    for node_id in history['outputs']:
        node_output = history['outputs'][node_id]
        images_output = []
        if 'images' in node_output:
            for image in node_output['images']:
                image_data = get_image(image['filename'], image['subfolder'], image['type'])
                # bytes 객체를 base64로 인코딩하여 JSON 직렬화 가능하게 변환
                if isinstance(image_data, bytes):
                    import base64
                    image_data = base64.b64encode(image_data).decode('utf-8')
                images_output.append(image_data)
        output_images[node_id] = images_output

    return output_images, prompt_id

def load_workflow(workflow_path):
    """워크플로우 파일을 로드하는 함수"""
    # 상대 경로인 경우 현재 파일 기준으로 절대 경로 변환
    if not os.path.isabs(workflow_path):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        workflow_path = os.path.join(current_dir, workflow_path)
    with open(workflow_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def cleanup_runtime_artifacts(task_id):
    """Cleanup endpoint-local artifacts after each task."""
    paths_to_clean = [
        os.path.abspath(task_id),
        '/ComfyUI/input',
        '/ComfyUI/output',
        '/ComfyUI/temp',
    ]

    for target in paths_to_clean:
        try:
            if not os.path.exists(target):
                continue

            # Remove contents only for shared ComfyUI dirs
            if target in ['/ComfyUI/input', '/ComfyUI/output', '/ComfyUI/temp']:
                for name in os.listdir(target):
                    path = os.path.join(target, name)
                    if os.path.isdir(path):
                        shutil.rmtree(path, ignore_errors=True)
                    else:
                        try:
                            os.remove(path)
                        except FileNotFoundError:
                            pass
            else:
                if os.path.isdir(target):
                    shutil.rmtree(target, ignore_errors=True)
                elif os.path.isfile(target):
                    os.remove(target)
        except Exception as cleanup_error:
            logger.warning(f"Cleanup warning for {target}: {cleanup_error}")

def collect_db_snapshot():
    runtime_root = os.getenv('RUNTIME_ROOT', '/dev/shm/comfy-runtime')
    db_paths = {
        'runtime': os.path.join(runtime_root, 'user', 'comfyui.db'),
        'legacy': '/ComfyUI/user/comfyui.db'
    }

    snapshot = {}
    for key, db_path in db_paths.items():
        try:
            if os.path.exists(db_path):
                snapshot[key] = {
                    'exists': True,
                    'size': os.path.getsize(db_path)
                }
            else:
                snapshot[key] = {
                    'exists': False,
                    'size': 0
                }
        except Exception as e:
            snapshot[key] = {'error': e.__class__.__name__}

    return snapshot


def diff_db_snapshot(before, after):
    out = {}
    for key in set(before.keys()) | set(after.keys()):
        b = before.get(key, {})
        a = after.get(key, {})
        out[key] = {
            'before': b,
            'after': a,
        }
        if isinstance(b, dict) and isinstance(a, dict) and 'size' in b and 'size' in a:
            out[key]['size_delta'] = a['size'] - b['size']
    return out

def collect_cleanup_state():
    """Collect post-cleanup state summary for logging."""
    state = {
        'history_count': None,
        'files': {},
        'db': {}
    }

    try:
        url = f"http://{server_address}:8188/history"
        with urllib.request.urlopen(url, timeout=5) as response:
            history = json.loads(response.read())
        state['history_count'] = len(history) if isinstance(history, dict) else -1
    except Exception as e:
        state['history_count'] = f"error:{e.__class__.__name__}"

    runtime_root = os.getenv('RUNTIME_ROOT', '/dev/shm/comfy-runtime')
    for folder in ['input', 'output', 'temp']:
        path = os.path.join(runtime_root, folder)
        try:
            state['files'][folder] = len(os.listdir(path)) if os.path.isdir(path) else 'missing'
        except Exception as e:
            state['files'][folder] = f"error:{e.__class__.__name__}"

    db_paths = {
        'runtime': os.path.join(runtime_root, 'user', 'comfyui.db'),
        'legacy': '/ComfyUI/user/comfyui.db'
    }
    for key, db_path in db_paths.items():
        try:
            if os.path.exists(db_path):
                state['db'][key] = {'exists': True, 'size': os.path.getsize(db_path)}
            else:
                state['db'][key] = {'exists': False}
        except Exception as e:
            state['db'][key] = {'error': e.__class__.__name__}

    return state

def handler(job):
    job_input = job.get("input", {})
    job_input = decrypt_secure_input(job_input)

    logger.info(f"Received job input (masked): {mask_job_input_for_log(job_input)}")
    task_id = f"task_{uuid.uuid4()}"
    prompt_id = None
    db_snapshot_before = collect_db_snapshot()

    try:

            # condition 이미지 입력 처리 (condition_image, condition_image_path, condition_image_url, condition_image_base64 중 하나만 사용)
            condition_image_path = None
            if "condition_image" in job_input:
                # condition_image 파라미터가 제공된 경우, 자동으로 타입 감지
                condition_image_data = job_input["condition_image"]
                if isinstance(condition_image_data, str):
                    if condition_image_data.startswith("http://") or condition_image_data.startswith("https://"):
                        condition_image_path = process_input(condition_image_data, task_id, "condition_image.jpg", "url")
                    elif os.path.exists(condition_image_data) or condition_image_data.startswith("/"):
                        condition_image_path = process_input(condition_image_data, task_id, "condition_image.jpg", "path")
                    else:
                        # Base64로 간주
                        condition_image_path = process_input(condition_image_data, task_id, "condition_image.jpg", "base64")
                else:
                    raise Exception("condition_image 파라미터는 문자열이어야 합니다.")
            elif "condition_image_path" in job_input:
                condition_image_path = process_input(job_input["condition_image_path"], task_id, "condition_image.jpg", "path")
            elif "condition_image_url" in job_input:
                condition_image_path = process_input(job_input["condition_image_url"], task_id, "condition_image.jpg", "url")
            elif "condition_image_base64" in job_input:
                condition_image_path = process_input(job_input["condition_image_base64"], task_id, "condition_image.jpg", "base64")

            # LoRA 확인
            lora_list = job_input.get("lora", [])
            has_lora = lora_list and len(lora_list) > 0
    
            # 워크플로우 파일 선택 (우선순위: condition_image > lora > 기본)
            if condition_image_path:
                workflow_file = "workflow/z_image_control.json"
                logger.info(f"Using control workflow: {workflow_file}")
            elif has_lora:
                workflow_file = "workflow/z_image_lora.json"
                logger.info(f"Using LoRA workflow: {workflow_file}")
            else:
                workflow_file = "workflow/z_image.json"
                logger.info(f"Using text-only workflow: {workflow_file}")

            prompt = load_workflow(workflow_file)

            # 공통 설정
            prompt_text = job_input.get("prompt", "")
            seed = job_input.get("seed", 533303727624653)
            steps = job_input.get("steps", 9)
            cfg = job_input.get("cfg", 1.0)
            width = job_input.get("width", 1024)
            height = job_input.get("height", 1024)
            negative_prompt = job_input.get("negative_prompt", job_input.get("negativePrompt", ""))
    
            # 해상도(폭/높이) 16배수 보정
            adjusted_width = to_nearest_multiple_of_16(width)
            adjusted_height = to_nearest_multiple_of_16(height)
            if adjusted_width != width:
                logger.info(f"Width adjusted to nearest multiple of 16: {width} -> {adjusted_width}")
            if adjusted_height != height:
                logger.info(f"Height adjusted to nearest multiple of 16: {height} -> {adjusted_height}")

            if condition_image_path:
                # z_image_control.json 워크플로우 설정
                # 노드 58: LoadImage (condition 이미지)
                prompt["58"]["inputs"]["image"] = condition_image_path
        
                # 노드 70:45: CLIPTextEncode (프롬프트)
                prompt["70:45"]["inputs"]["text"] = prompt_text
        
                # 노드 70:44: KSampler (seed, steps, cfg)
                prompt["70:44"]["inputs"]["seed"] = seed
                prompt["70:44"]["inputs"]["steps"] = steps
                prompt["70:44"]["inputs"]["cfg"] = cfg
        
                # 노드 57: Canny (low_threshold, high_threshold) - 선택적
                if "canny_low_threshold" in job_input:
                    prompt["57"]["inputs"]["low_threshold"] = job_input["canny_low_threshold"]
                if "canny_high_threshold" in job_input:
                    prompt["57"]["inputs"]["high_threshold"] = job_input["canny_high_threshold"]
        
                # 노드 70:60: QwenImageDiffsynthControlnet (strength) - 선택적
                if "controlnet_strength" in job_input:
                    prompt["70:60"]["inputs"]["strength"] = job_input["controlnet_strength"]
        
                # 노드 70:41: EmptySD3LatentImage는 70:69에서 자동으로 크기를 가져오므로 설정 불필요
        
                logger.info("Control workflow 설정 완료: condition_image=..., prompt=...")
            elif has_lora:
                # z_image_lora.json 워크플로우 설정
                # 노드 58: PrimitiveStringMultiline (프롬프트)
                prompt["58"]["inputs"]["value"] = prompt_text
        
                # 노드 59:13: EmptySD3LatentImage (width, height)
                prompt["59:13"]["inputs"]["width"] = adjusted_width
                prompt["59:13"]["inputs"]["height"] = adjusted_height
        
                # 노드 59:3: KSampler (seed, steps, cfg)
                prompt["59:3"]["inputs"]["seed"] = seed
                prompt["59:3"]["inputs"]["steps"] = steps
                prompt["59:3"]["inputs"]["cfg"] = cfg
        
                # 노드 59:35: LoraLoaderModelOnly (lora_name, strength_model)
                # 첫 번째 LoRA만 사용 (나중에 여러 개 지원 가능)
                first_lora = lora_list[0]
                if isinstance(first_lora, list) and len(first_lora) >= 2:
                    lora_path = first_lora[0]
                    lora_strength = first_lora[1]
                else:
                    raise Exception("LoRA 형식이 올바르지 않습니다. [파일경로, strength] 형태여야 합니다.")
        
                prompt["59:35"]["inputs"]["lora_name"] = lora_path
                prompt["59:35"]["inputs"]["strength_model"] = lora_strength
        
                logger.info("LoRA workflow 설정 완료: lora=..., strength=..., prompt=...")
            else:
                # z_image.json 워크플로우 설정
                # 노드 45: CLIPTextEncode (프롬프트)
                prompt["45"]["inputs"]["text"] = prompt_text
        
                # 노드 44: KSampler (seed, steps, cfg)
                prompt["44"]["inputs"]["seed"] = seed
                prompt["44"]["inputs"]["steps"] = steps
                prompt["44"]["inputs"]["cfg"] = cfg
        
                # 노드 41: EmptySD3LatentImage (width, height)
                prompt["41"]["inputs"]["width"] = adjusted_width
                prompt["41"]["inputs"]["height"] = adjusted_height
        
                logger.info("Text-only workflow 설정 완료: prompt=...")

            ws_url = f"ws://{server_address}:8188/ws?clientId={client_id}"
            logger.info(f"Connecting to WebSocket: {ws_url}")
    
            # 먼저 HTTP 연결이 가능한지 확인
            http_url = f"http://{server_address}:8188/"
            logger.info(f"Checking HTTP connection to: {http_url}")
    
            # HTTP 연결 확인 (최대 1분)
            max_http_attempts = 180
            for http_attempt in range(max_http_attempts):
                try:
                    import urllib.request
                    response = urllib.request.urlopen(http_url, timeout=5)
                    logger.info(f"HTTP 연결 성공 (시도 {http_attempt+1})")
                    break
                except Exception as e:
                    logger.warning(f"HTTP 연결 실패 (시도 {http_attempt+1}/{max_http_attempts}): {e}")
                    if http_attempt == max_http_attempts - 1:
                        raise Exception("ComfyUI 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.")
                    time.sleep(1)
    
            ws = websocket.WebSocket()
            # 웹소켓 연결 시도 (최대 3분)
            max_attempts = int(180/5)  # 3분 (5초에 한 번씩 시도)
            for attempt in range(max_attempts):
                try:
                    ws.connect(ws_url)
                    logger.info(f"웹소켓 연결 성공 (시도 {attempt+1})")
                    break
                except Exception as e:
                    logger.warning(f"웹소켓 연결 실패 (시도 {attempt+1}/{max_attempts}): {e}")
                    if attempt == max_attempts - 1:
                        raise Exception("웹소켓 연결 시간 초과 (3분)")
                    time.sleep(5)
            images, prompt_id = get_images(ws, prompt)
            ws.close()

            # 이미지가 없는 경우 처리
            if not images:
                return {"error": "이미지를 생성할 수 없습니다."}
    
            # 첫 번째 이미지 반환
            for node_id in images:
                if images[node_id]:
                    image_data = images[node_id][0]
            
                    if job_input.get("return_url", False):
                        # R2 업로드
                        file_name = f"{task_id}.png"
                        image_url = upload_to_r2(image_data, file_name)
                        if image_url:
                            return {"image_url": image_url}
                        else:
                             logger.warning("R2 업로드 실패, Base64 이미지를 반환합니다.")

                    return {"image": image_data}
    
            return {"error": "이미지를 찾을 수 없습니다."}
    finally:
        # Endpoint-like cleanup: remove history + runtime dirs + free memory
        try:
            cleanup_script = os.getenv('FINISH_CLEANUP_SCRIPT', '/scripts/finish_cleanup.sh')
            if os.path.exists(cleanup_script):
                subprocess.run([
                    cleanup_script,
                    prompt_id or ''
                ], check=False, env={**os.environ, 'COMFY_BASE_URL': f'http://{server_address}:8188'})
        except Exception as cleanup_script_error:
            logger.warning(f"Cleanup script warning: {cleanup_script_error}")

        cleanup_runtime_artifacts(task_id)

        try:
            cleanup_state = collect_cleanup_state()
            db_snapshot_after = collect_db_snapshot()
            db_diff = diff_db_snapshot(db_snapshot_before, db_snapshot_after)
            logger.info(
                f"Cleanup verify: history={cleanup_state['history_count']}, "
                f"files={cleanup_state['files']}, db_diff={db_diff}"
            )
        except Exception as cleanup_verify_error:
            logger.warning(f"Cleanup verify warning: {cleanup_verify_error}")

runpod.serverless.start({"handler": handler})