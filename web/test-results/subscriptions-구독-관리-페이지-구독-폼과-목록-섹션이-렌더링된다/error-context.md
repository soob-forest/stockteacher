# Page snapshot

```yaml
- generic [ref=e2]:
  - complementary [ref=e3]:
    - heading "StockTeacher" [level=1] [ref=e4]
    - navigation [ref=e5]:
      - link "구독 관리" [ref=e6] [cursor=pointer]:
        - /url: /subscriptions
      - link "리포트" [ref=e7] [cursor=pointer]:
        - /url: /reports
      - link "즐겨찾기" [ref=e8] [cursor=pointer]:
        - /url: /reports/favorites
  - main [ref=e9]:
    - generic [ref=e10]:
      - generic [ref=e11]:
        - heading "구독 종목 등록" [level=2] [ref=e12]
        - paragraph [ref=e13]: 감시할 종목 티커와 리포트 수신 시간을 선택하세요.
        - generic [ref=e14]:
          - generic [ref=e15]:
            - generic [ref=e16]: 종목 티커
            - textbox "종목 티커" [ref=e17]:
              - /placeholder: "예: AAPL"
          - generic [ref=e18]:
            - generic [ref=e19]: 알림 윈도우
            - combobox "알림 윈도우" [ref=e20]:
              - option "당일 즉시" [selected]
              - option "매일 장 시작 전"
              - option "매일 장 마감 후"
              - option "주간 요약"
          - button "구독 추가" [ref=e22] [cursor=pointer]
      - generic [ref=e23]:
        - generic [ref=e24]:
          - heading "구독 목록" [level=2] [ref=e25]
          - generic [ref=e26]: 활성 0
        - generic [ref=e27]: 등록된 종목이 없습니다.
```