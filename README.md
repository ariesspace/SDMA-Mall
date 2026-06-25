# SDMA Mall

월 1회만 열어 쓰기 좋은 가벼운 포인트 쇼핑몰입니다. Python 표준 라이브러리와 SQLite만 사용해서 작은 VPS에서도 Docker 컨테이너를 `up/down` 하기 쉽도록 구성했습니다.

## 실행

```powershell
cd C:\new\SDMAmall
docker compose up --build -d
```

브라우저:

```text
http://localhost:8090/mall
```

끄기:

```powershell
docker compose down
```

데이터는 `data/sdma-mall.sqlite3`에 남습니다. 컨테이너를 내려도 사용자, 상품, 구매 내역은 유지됩니다.

## 관리자 코드

운영 서버에서는 `.env` 파일을 만들어 기본값을 꼭 바꾸세요.

```text
SDMA_MALL_ADMIN_CODE=원하는_관리자_코드
```

첫 화면 왼쪽 아래 외계인 버튼을 5번 누르면 관리자 코드 팝업이 열립니다. 코드가 맞으면 `/mall/admin`으로 이동합니다.

## 운영 흐름

1. 월 행사 전에 `docker compose up --build -d`로 mall을 엽니다.
2. 관리자 페이지에서 사번, 이름, 팀, 점수를 등록합니다.
3. 관리자 페이지에서 상품명, 가격, 원가, 재고, 이미지 URL을 등록합니다.
4. 사용자는 첫 화면에서 `나는 물건을 본다`를 누르고 사번으로 로그인합니다.
5. 사용자는 장바구니에 상품을 담고 결제합니다.
6. 행사 종료 후 관리자 페이지에서 영수증 내역을 복사하고, 서버에서는 `docker compose down`으로 내립니다.

## nginx 예시

`sdma.site/mall/`로 붙일 때의 기본 예시입니다.

```nginx
location /mall/ {
    proxy_pass http://127.0.0.1:8090/mall/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```
