# 교사용 EV3 Xbox Relay — 문서 안내

> 2026-10-12 정리. 이 저장소는 **현재 운영 중인 교사용 Relay와 EV3 Xbox 수신 서비스**를 관리합니다.

- [README](../README.md) — Windows·Mac `git clone`, `Start-Relay.cmd`·`Start-Relay.command` 자동 설치/실행
- [대회 얼라이언스 중계·Wi-Fi 운영](relay/alliance-relay.md) — Robot ID, 1팀 3대, 공용 AP·팀별 AP 선택 및 실기 검증 조건
- [EV3 상주 Xbox 서비스](reference/xbox_service.md) — systemd 서비스 설치·설정·Robot ID 변경
- [실기·자동 설치 테스트 로그](TEST_LOG.md) — 실제 확인한 항목과 남은 검증
- [학생용 VSCode 및 Python 가이드](https://github.com/qmercury/student_ev3xbox/blob/main/docs/README.md)
- [전체 개발 현황과 다음 테스트](https://github.com/qmercury/ev3XboxConnect/blob/main/docs/NEXT_STEPS.md)

**검증 상태:** Mac mini에서 Relay 실행 성공, GitHub Windows/macOS 패키지 설치 테스트 성공. Windows 실물 Xbox 버튼/축 맵핑, Xbox·EV3 3대 동시 중계, 인터넷 없는 AP 제품 선정·경기 환경 시험은 완료되지 않았습니다. 대회 네트워크 설계는 미확정입니다.
