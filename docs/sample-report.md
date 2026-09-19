# 합성 fixture 결과

실제 API 호출 없이 규칙 기반으로 검사한 예시입니다.

{
  "CONFIRMED": 1,
  "REFUTED": 1,
  "UNCONFIRMED": 1,
  "NEEDS_HUMAN": 1
}

빈 배열 평균 계산을 의심했습니다. 호출부에서 막을 가능성을 반대 검토했고, 허용된 함수 본문을 빈 배열로 3회 계산했습니다. 세 번 모두 0 나눗셈이 발생하여 이 함수/입력 범위에서 CONFIRMED로 판정했습니다. 앱 전체의 도달 가능성은 별도 확인이 필요합니다.

[전체 화면 예시](sample-report.html)
