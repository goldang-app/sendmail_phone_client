#!/usr/bin/env python3
"""
다중 디바이스 이메일 발송 관리 시스템 - 클라이언트
간편한 메뉴 인터페이스 버전
"""

import asyncio
import aiohttp
import json
import sys
import os
import platform
import subprocess
import socket
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
from ip_manager import IPManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 설정 파일 경로
CONFIG_DIR = Path("config")
CONFIG_FILE = CONFIG_DIR / "config.json"

class Config:
    """설정 관리 클래스"""

    def __init__(self):
        self.config_dir = CONFIG_DIR
        self.config_file = CONFIG_FILE
        self.config = self.load_config()

    def load_config(self) -> dict:
        """설정 파일 로드"""
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)

        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return self.default_config()
        else:
            return self.default_config()

    def default_config(self) -> dict:
        """기본 설정"""
        return {
            "server_ip": "http://121.175.50.3:8000",  # 기본값을 서버 공인 IP로 설정
            "device_name": self.generate_device_name(),
            "last_connected": None,
            "auto_connect": False
        }

    def generate_device_name(self) -> str:
        """디바이스 이름 자동 생성"""
        hostname = socket.gethostname()[:10]
        return f"Device_{hostname}"

    def save_config(self):
        """설정 저장"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ 설정 저장 실패: {e}")
            return False

    def get(self, key: str, default=None):
        """설정 값 가져오기"""
        return self.config.get(key, default)

    def set(self, key: str, value):
        """설정 값 저장"""
        self.config[key] = value
        self.save_config()

class DeviceAgent:
    """디바이스 에이전트 - 서버와 통신하며 명령 수행"""

    def __init__(self, server_url: str, device_name: str):
        self.server_url = server_url.rstrip('/')
        self.device_id = self.generate_device_id()
        self.device_name = device_name
        self.running = True
        self.current_ip = None
        self.platform = self.detect_platform()

    def generate_device_id(self) -> str:
        """고유 디바이스 ID 생성"""
        try:
            if os.path.exists('/data/data/com.termux'):
                try:
                    result = subprocess.run(
                        ['termux-telephony-deviceinfo'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        data = json.loads(result.stdout)
                        device_id = data.get('device_id', '')
                        if device_id:
                            return f"Phone_{device_id[-8:]}"
                except:
                    pass

            hostname = socket.gethostname()
            return f"Device_{hostname[:10]}"

        except Exception as e:
            return f"Device_{int(time.time() % 100000)}"

    def detect_platform(self) -> str:
        """플랫폼 감지"""
        if os.path.exists('/data/data/com.termux'):
            return "termux"
        elif platform.system() == "Linux":
            return "linux"
        elif platform.system() == "Windows":
            return "windows"
        elif platform.system() == "Darwin":
            return "macos"
        else:
            return "unknown"

    async def get_current_ip(self) -> str:
        """현재 공인 IP 조회"""
        try:
            services = [
                'https://api.ipify.org',
                'https://ifconfig.me/ip',
                'https://ipecho.net/plain',
            ]

            async with aiohttp.ClientSession() as session:
                for service in services:
                    try:
                        async with session.get(service, timeout=5) as resp:
                            if resp.status == 200:
                                ip = (await resp.text()).strip()
                                if self.validate_ip(ip):
                                    return ip
                    except:
                        continue

            result = subprocess.run(
                ['curl', '-s', 'ifconfig.me'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                ip = result.stdout.strip()
                if self.validate_ip(ip):
                    return ip

            return "Unknown"

        except Exception as e:
            return "Unknown"

    def validate_ip(self, ip: str) -> bool:
        """IP 주소 유효성 검사"""
        try:
            parts = ip.split('.')
            return len(parts) == 4 and all(0 <= int(part) <= 255 for part in parts)
        except:
            return False

    async def change_ip(self) -> Dict[str, Any]:
        """IP 변경 수행 (IPManager 사용)"""
        print("\n🔄 IP 변경 시작...")

        # IPManager 인스턴스 생성
        ip_manager = IPManager()

        # IP 변경 실행
        result = await ip_manager.change_ip()

        # 결과 출력
        if result["success"]:
            print(f"   ✅ IP 변경 성공: {result['old_ip']} → {result['new_ip']} ({result['change_duration']:.1f}초)")
            self.current_ip = result['new_ip']
        else:
            print(f"   ❌ IP 변경 실패: {result['old_ip']} → {result['new_ip']}")

        return result

    async def register(self) -> bool:
        """서버에 디바이스 등록"""
        try:
            self.current_ip = await self.get_current_ip()

            data = {
                "device_id": self.device_id,
                "device_name": self.device_name,
                "current_ip": self.current_ip,
                "platform": self.platform
            }

            print(f"📤 등록 요청 전송:")
            print(f"   - Device ID: {self.device_id}")
            print(f"   - Device Name: {self.device_name}")
            print(f"   - Current IP: {self.current_ip}")
            print(f"   - Platform: {self.platform}")
            print(f"   - Server URL: {self.server_url}/api/register")

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.server_url}/api/register",
                    json=data,
                    timeout=10
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        print(f"✅ 서버 등록 성공: {self.device_name}")
                        print(f"   서버 응답: {result}")
                        return True
                    else:
                        error_text = await resp.text()
                        print(f"❌ 서버 등록 실패: HTTP {resp.status}")
                        print(f"   에러 메시지: {error_text}")
                        return False

        except Exception as e:
            print(f"❌ 연결 오류: {e}")
            logger.error(f"Registration failed: {e}", exc_info=True)
            return False

    async def send_status(self) -> None:
        """서버에 상태 보고"""
        try:
            self.current_ip = await self.get_current_ip()

            data = {
                "device_id": self.device_id,
                "current_ip": self.current_ip,
                "status": "online"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.server_url}/api/status",
                    json=data,
                    timeout=10
                ) as resp:
                    pass

        except:
            pass

    async def check_commands(self) -> None:
        """서버에서 명령 확인 및 실행"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.server_url}/api/commands/{self.device_id}",
                    timeout=10
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        commands = data.get("commands", [])

                        for cmd in commands:
                            await self.execute_command(cmd)

        except:
            pass

    async def execute_command(self, command: Dict[str, Any]) -> None:
        """명령 실행"""
        cmd_type = command.get("command")

        if cmd_type == "change_ip":
            print(f"\n📡 서버 명령: IP 변경")
            result = await self.change_ip()

            report = {
                "device_id": self.device_id,
                "old_ip": result["old_ip"],
                "new_ip": result["new_ip"],
                "change_duration": result["change_duration"],
                "success": result["success"],
                "timestamp": datetime.now().isoformat()
            }

            async with aiohttp.ClientSession() as session:
                await session.post(
                    f"{self.server_url}/api/report/ip_change",
                    json=report,
                    timeout=10
                )

        elif cmd_type == "test":
            print(f"📡 서버 명령: 테스트")
            await self.send_status()

        elif cmd_type == "stop":
            print(f"📡 서버 명령: 정지")
            self.running = False

    async def run(self) -> None:
        """메인 실행 루프"""
        print(f"\n🚀 에이전트 시작")
        print(f"   서버: {self.server_url}")
        print(f"   디바이스: {self.device_name}")
        print(f"   플랫폼: {self.platform}")

        registered = await self.register()
        if not registered:
            print("⚠️ 서버 등록 실패, 재시도 예정...")

        print("\n✅ 연결됨! 명령 대기중... (중지: Ctrl+C)\n")

        status_interval = 30
        command_interval = 5
        last_status = 0
        last_command = 0

        while self.running:
            try:
                current_time = time.time()

                if current_time - last_command >= command_interval:
                    await self.check_commands()
                    last_command = current_time

                if current_time - last_status >= status_interval:
                    await self.send_status()
                    last_status = current_time

                await asyncio.sleep(1)

            except KeyboardInterrupt:
                print("\n👋 중지됨")
                break
            except Exception as e:
                await asyncio.sleep(5)

        print("🛑 에이전트 종료")


class MenuInterface:
    """메뉴 인터페이스"""

    def __init__(self):
        self.config = Config()
        self.agent = None

    def clear_screen(self):
        """화면 지우기"""
        os.system('clear' if os.name != 'nt' else 'cls')

    def print_header(self):
        """헤더 출력"""
        self.clear_screen()
        print("=" * 50)
        print("     📱 다중 디바이스 관리 시스템 - 클라이언트")
        print("=" * 50)

    def main_menu(self):
        """메인 메뉴"""
        while True:
            self.print_header()
            print("\n📋 메인 메뉴\n")
            print("  1. 🔗 서버 연결 (명령 대기)")
            print("  2. ⚙️  서버 IP 설정")
            print("  3. 🔄 IP 변경 테스트 (반복 실행)")
            print("  4. 📝 디바이스 이름 설정")
            print("  5. ℹ️  현재 설정 보기")
            print("  0. 🚪 종료")
            print()

            choice = input("선택 [0-5]: ").strip()

            if choice == "1":
                self.connect_to_server()
            elif choice == "2":
                self.set_server_ip()
            elif choice == "3":
                self.ip_change_loop()
            elif choice == "4":
                self.set_device_name()
            elif choice == "5":
                self.show_config()
            elif choice == "0":
                print("\n👋 프로그램을 종료합니다.")
                break
            else:
                print("❌ 잘못된 선택입니다.")
                time.sleep(1)

    def set_server_ip(self):
        """서버 IP 설정"""
        self.print_header()
        print("\n⚙️ 서버 IP 설정\n")
        print(f"현재 서버 IP: {self.config.get('server_ip')}\n")

        print("입력 예시:")
        print("  - 로컬: http://localhost:8000")
        print("  - 네트워크: http://192.168.1.100:8000")
        print("  - 공인 IP: http://121.175.50.3:8000")
        print("  - ngrok: https://abc123.ngrok.io")
        print()

        new_ip = input("새 서버 주소 (엔터=취소): ").strip()

        if new_ip:
            # http:// 또는 https://가 없으면 추가
            if not new_ip.startswith(('http://', 'https://')):
                # 포트가 포함되어 있지 않으면 8000 추가
                if ':' not in new_ip.split('/')[-1]:
                    new_ip = f"http://{new_ip}:8000"
                else:
                    new_ip = f"http://{new_ip}"

            self.config.set('server_ip', new_ip)
            print(f"\n✅ 서버 주소 저장됨: {new_ip}")

            # 연결 테스트
            print("🔍 서버 연결 테스트 중...")
            import requests
            try:
                resp = requests.get(f"{new_ip}/api/devices", timeout=5)
                if resp.status_code == 200:
                    print("✅ 서버 연결 성공!")
                else:
                    print(f"⚠️ 서버 응답 상태: {resp.status_code}")
            except requests.ConnectionError:
                print("❌ 서버에 연결할 수 없습니다. 주소와 포트를 확인하세요.")
            except requests.Timeout:
                print("⏰ 연결 시간 초과. 서버가 실행중인지 확인하세요.")
            except Exception as e:
                print(f"⚠️ 연결 테스트 실패: {e}")
        else:
            print("\n❌ 취소됨")

        time.sleep(3)

    def set_device_name(self):
        """디바이스 이름 설정"""
        self.print_header()
        print("\n📝 디바이스 이름 설정\n")
        print(f"현재 이름: {self.config.get('device_name')}\n")

        new_name = input("새 디바이스 이름 (엔터=취소): ").strip()

        if new_name:
            self.config.set('device_name', new_name)
            print(f"\n✅ 디바이스 이름 저장됨: {new_name}")
        else:
            print("\n❌ 취소됨")

        time.sleep(2)

    def show_config(self):
        """현재 설정 표시"""
        self.print_header()
        print("\n📋 현재 설정\n")
        print(f"  🌐 서버 주소: {self.config.get('server_ip')}")
        print(f"  📱 디바이스 이름: {self.config.get('device_name')}")
        print(f"  ⏰ 마지막 연결: {self.config.get('last_connected', '없음')}")
        print(f"  📁 설정 파일: {CONFIG_FILE}")
        print()
        input("엔터를 눌러 계속...")

    def ip_change_loop(self):
        """IP 변경 반복 테스트 및 서버 기록"""
        self.print_header()
        print("\n🔄 IP 변경 반복 테스트\n")

        server_ip = self.config.get('server_ip')
        device_name = self.config.get('device_name')

        print(f"서버: {server_ip}")
        print(f"디바이스: {device_name}")
        print()

        try:
            count = input("IP 변경 횟수 (기본: 10회): ").strip()
            if not count:
                count = 10
            else:
                count = int(count)

            interval = input("변경 간격(초) (기본: 30초): ").strip()
            if not interval:
                interval = 30
            else:
                interval = int(interval)

        except ValueError:
            print("❌ 잘못된 입력입니다.")
            time.sleep(2)
            return

        print(f"\n📊 설정: {count}회 변경, {interval}초 간격")
        confirm = input("시작하시겠습니까? [y/N]: ").strip().lower()

        if confirm == 'y':
            agent = DeviceAgent(server_ip, device_name)
            asyncio.run(self._ip_change_loop(agent, count, interval))

            print("\n✅ IP 변경 테스트 완료!")
            print("서버 대시보드에서 결과를 확인하세요.")
        else:
            print("\n❌ 취소됨")

        time.sleep(2)

    async def _ip_change_loop(self, agent, count, interval):
        """IP 변경 반복 실행 비동기 함수"""
        # 먼저 서버에 등록
        print("\n📡 서버 연결중...")
        registered = await agent.register()

        if not registered:
            print("❌ 서버 연결 실패!")
            return

        print("✅ 서버 연결 성공!")
        print(f"\n🔄 IP 변경 시작 (총 {count}회)\n")

        success_count = 0
        fail_count = 0

        for i in range(count):
            print(f"\n===== [{i+1}/{count}] IP 변경 =====")

            # IP 변경 실행
            result = await agent.change_ip()

            # 서버에 결과 보고
            report = {
                "device_id": agent.device_id,
                "old_ip": result["old_ip"],
                "new_ip": result["new_ip"],
                "change_duration": result["change_duration"],
                "success": result["success"],
                "timestamp": datetime.now().isoformat()
            }

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{agent.server_url}/api/report/ip_change",
                        json=report,
                        timeout=10
                    ) as resp:
                        if resp.status == 200:
                            print("   📤 서버에 결과 전송 완료")
                        else:
                            print("   ⚠️ 서버 전송 실패")
            except Exception as e:
                print(f"   ⚠️ 서버 전송 오류: {e}")

            if result["success"]:
                success_count += 1
            else:
                fail_count += 1

            # 마지막이 아니면 대기
            if i < count - 1:
                print(f"\n⏰ {interval}초 대기중...")
                await asyncio.sleep(interval)

        # 최종 통계
        print("\n" + "=" * 40)
        print("📊 최종 결과:")
        print(f"  ✅ 성공: {success_count}회")
        print(f"  ❌ 실패: {fail_count}회")
        print(f"  📈 성공률: {(success_count/count)*100:.1f}%")
        print("=" * 40)

    def connect_to_server(self):
        """서버 연결"""
        self.print_header()
        print("\n🔗 서버 연결\n")

        server_ip = self.config.get('server_ip')
        device_name = self.config.get('device_name')

        print(f"서버: {server_ip}")
        print(f"디바이스: {device_name}")
        print()

        confirm = input("연결하시겠습니까? [y/N]: ").strip().lower()

        if confirm == 'y':
            self.config.set('last_connected', datetime.now().isoformat())

            agent = DeviceAgent(server_ip, device_name)

            try:
                asyncio.run(agent.run())
            except KeyboardInterrupt:
                print("\n\n👋 연결 종료됨")
                time.sleep(1)
        else:
            print("\n❌ 취소됨")
            time.sleep(1)


def main():
    """메인 함수"""
    menu = MenuInterface()

    try:
        menu.main_menu()
    except KeyboardInterrupt:
        print("\n\n👋 프로그램 종료")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")


if __name__ == "__main__":
    main()