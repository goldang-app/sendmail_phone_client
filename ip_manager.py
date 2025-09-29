#!/usr/bin/env python3
"""
IP 변경 관리자 - sendmail_by_phone에서 가져온 코드 (수정 없이 그대로 사용)
"""
import subprocess
import time
import requests
import os
import json
import asyncio

def get_public_ipv4():
    """공인아이피를 가져오는 함수

    Returns:
        str: 현재 공인 IPv4 주소
    """
    try:
        response = requests.get("https://ipv4.icanhazip.com", timeout=10)
        return response.text.strip()
    except requests.RequestException:
        return None

def record_ip(ip):
    """IP를 total_ips.txt 파일에 기록하는 함수

    Args:
        ip (str): 기록할 IP 주소

    Returns:
        bool: 새로운 IP가 기록되었으면 True, 이미 존재하면 False
    """
    # settings 디렉토리 확인 및 생성
    settings_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings")
    os.makedirs(settings_dir, exist_ok=True)

    ip_file = os.path.join(settings_dir, "total_ips.txt")

    # 파일이 없으면 생성
    if not os.path.exists(ip_file):
        with open(ip_file, "w") as f:
            f.write(f"{ip}\n")
        return True

    # 파일이 있으면 IP 중복 확인
    with open(ip_file, "r") as f:
        ips = f.read().splitlines()

    # IP가 이미 존재하는지 확인
    if ip in ips:
        return False

    # 새 IP 추가
    with open(ip_file, "a") as f:
        f.write(f"{ip}\n")
    return True

def change_mobile_ip_at_phone():
    """모바일 아이피를 변경하는 함수

    Returns:
        str: 변경된 IP 주소
    """
    def toggle_airplane_mode(state):
        try:
            if state == 'on':
                subprocess.run(['su', '-c', 'settings put global airplane_mode_on 1'],
                              check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(['su', '-c', 'am broadcast -a android.intent.action.AIRPLANE_MODE --ez state true'],
                              check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif state == 'off':
                subprocess.run(['su', '-c', 'settings put global airplane_mode_on 0'],
                              check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(['su', '-c', 'am broadcast -a android.intent.action.AIRPLANE_MODE --ez state false'],
                              check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            print(f"❌ 비행기 모드 전환 실패: {e}")

    def reset_data():
        try:
            print("🔄 모바일 데이터 리셋 중...")
            subprocess.run(["su", "-c", "svc data disable"],
                          check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1)
            subprocess.run(["su", "-c", "svc data enable"],
                          check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(1)
        except subprocess.CalledProcessError as e:
            print(f"❌ 모바일 데이터 리셋 실패: {e}")

    # 알박기 간격과 디바이스 이름 정보 가져오기
    albakgi_interval = 0
    device_name = "Unknown"

    try:
        # config.json에서 정보 가져오기
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                device_name = config.get('device_name', 'Unknown')
                albakgi_interval = config.get('albakgi_interval', 300)  # 알박기 간격 설정값 가져오기
    except Exception as e:
        print(f"정보 로드 오류: {e}")

    # 현재 IP 먼저 확인
    old_ip = get_public_ipv4()
    print(f"🌐 현재 IP: {old_ip}")

    # 비행기 모드 활성화 → 비활성화 → 데이터 리셋
    print(f"🔄 비행기모드 전환중...")
    print(f"   📱 디바이스: {device_name}")
    toggle_airplane_mode('on')
    time.sleep(3)
    toggle_airplane_mode('off')
    time.sleep(4)
    print("🔄 모바일 IP 변경 시도 중...")

    # IP를 받아올 수 있을 때까지 최대 30초 대기
    max_attempts = 15
    attempt = 0
    while attempt < max_attempts:
        new_ip = get_public_ipv4()
        if new_ip:
            is_new = record_ip(new_ip)
            print(f"✅ 변경된 IP: {new_ip}")

            # IP 기록 결과 및 통계 출력
            settings_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings")
            ip_file = os.path.join(settings_dir, "total_ips.txt")

            if os.path.exists(ip_file):
                with open(ip_file, "r") as f:
                    total_ips = len(f.read().splitlines())
            else:
                total_ips = 1

            if is_new:
                print(f"📝 새 IP 기록 완료")
            else:
                print(f"⚠️ 이미 기록된 IP 기록하지 않습니다.")

            print(f"📊 현재까지 저장된 전체 IP 개수: {total_ips}개")
            return new_ip

        print(f"⏳ IP 확인 대기 중... ({attempt + 1}/{max_attempts})")
        time.sleep(2)
        attempt += 1

    print("❌ IP 확인 실패: 시간 초과")
    return None

# IPManager 클래스는 기존 main.py와의 호환성을 위해 유지
class IPManager:
    """IP 변경 관리자 클래스 (호환성 유지용)"""

    async def change_ip(self):
        """IP 변경 메서드"""
        start_time = time.time()

        # 현재 IP 가져오기
        old_ip = get_public_ipv4()
        if not old_ip:
            old_ip = "Unknown"

        # IP 변경 실행
        new_ip = change_mobile_ip_at_phone()

        # 결과 반환
        change_duration = time.time() - start_time

        if new_ip and new_ip != old_ip:
            return {
                "success": True,
                "old_ip": old_ip,
                "new_ip": new_ip,
                "change_duration": change_duration
            }
        else:
            return {
                "success": False,
                "old_ip": old_ip,
                "new_ip": new_ip if new_ip else "Failed",
                "change_duration": change_duration
            }

if __name__ == "__main__":
    change_mobile_ip_at_phone()