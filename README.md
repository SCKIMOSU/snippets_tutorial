# snippets_tutorial

> Django REST Framework 튜토리얼 — Class 4: 인증과 권한
>
> 풀스택서비스컴퓨팅 강의자료 · 국민대학교 소프트웨어학부

DRF의 핵심 패턴 — `GenericAPIView + Mixin`, `perform_create`, `ReadOnlyField`, 커스텀 `BasePermission` — 을 Snippet 모델 예제로 학습하고, 30개 단위 테스트로 모든 동작을 검증하는 강의용 저장소입니다.

---

## 학습 목표

이 저장소를 따라 끝까지 작성하면 다음을 이해하게 됩니다.

| # | 주제 | 핵심 개념 |
|---|------|----------|
| 1 | View 계층 책임 분리 | `GenericAPIView`(데이터 재료) ↔ `Mixin`(워크플로우) |
| 2 | 소유자 자동 주입 | `perform_create(self, serializer): serializer.save(owner=self.request.user)` |
| 3 | 소유자 위조 차단 | `owner = serializers.ReadOnlyField(source='owner.username')` |
| 4 | 객체 단위 권한 | `IsOwnerOrReadOnly` 커스텀 권한 + `SAFE_METHODS` 분기 |
| 5 | 테스트 전략 | 단위 격리 (12) + API 통합 (18) = 30개 테스트 |

---

## 사전 요구사항

| 항목 | 버전 |
|------|------|
| Python | 3.8 이상 |
| Django | 4.x |
| djangorestframework | 3.14+ |
| Git | 2.x |

---

## 빠른 시작

```bash
# 1. 클론
git clone https://github.com/SCKIMOSU/snippets_tutorial.git
cd tutorialclass4

# 2. 가상환경
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. 의존성 설치
pip install -r requirements.txt    # requirements.txt가 없다면:
# pip install django djangorestframework

# 4. DB 초기화
python manage.py migrate

# 5. 관리자 계정 생성
python manage.py createsuperuser

# 6. 개발 서버 실행
python manage.py runserver 8010
```

브라우저에서 http://127.0.0.1:8010/snippets/ 로 접속하면 DRF Browsable API가 표시됩니다.

---

## 테스트 실행

```bash
# 전체 테스트 (30개)
python manage.py test snippets -v 2

# 특정 클래스만
python manage.py test snippets.tests.SnippetCreateTest

# 커버리지 측정
pip install coverage
coverage run --source=snippets manage.py test snippets
coverage report -m
```

예상 결과:

```
Found 30 test(s).
...
Ran 30 tests in ~1s
OK
```

---

## 프로젝트 구조

```
tutorialclass4/
├── manage.py
├── requirements.txt
├── README.md
├── tutorialclass4/              # 프로젝트 설정
│   ├── settings.py
│   └── urls.py
└── snippets/                    # Snippet 앱
    ├── models.py                # Snippet (title, code, linenos, language, style, owner)
    ├── serializers.py           # SnippetSerializer (owner = ReadOnlyField)
    ├── permissions.py           # IsOwnerOrReadOnly
    ├── views.py                 # SnippetList, SnippetDetail
    ├── urls.py
    ├── tests.py                 # 30 unit tests
    └── migrations/
```

---

## 핵심 패턴 3가지

### 1. View — `perform_create`로 소유자 자동 주입

```python
# snippets/views.py
class SnippetList(generics.ListCreateAPIView):
    queryset = Snippet.objects.all()
    serializer_class = SnippetSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)   # ← 한 줄로 소유자 결정
```

### 2. Serializer — `ReadOnlyField`로 입력 차단

```python
# snippets/serializers.py
class SnippetSerializer(serializers.ModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')

    class Meta:
        model = Snippet
        fields = ['id', 'title', 'code', 'linenos',
                  'language', 'style', 'owner']
```

### 3. Permission — 소유자만 수정·삭제 가능

```python
# snippets/permissions.py
class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True                            # 읽기는 모두 허용
        return obj.owner == request.user           # 쓰기는 소유자만
```

---

## 테스트 30선의 두 축

| 영역 | 클래스 | 개수 | 검증 |
|------|-------|:---:|------|
| **단위 격리** | `SnippetSerializerTest` | 3 | ReadOnlyField의 선언·출력·입력 무시 |
| **단위 격리** | `IsOwnerOrReadOnlyUnitTest` | 9 | `has_object_permission()` 직접 호출 |
| **API 통합** | `SnippetListReadTest` | 2 | GET /snippets/ — 익명 허용 |
| **API 통합** | `SnippetCreateTest` | 5 | POST + `perform_create` + 위조 차단 |
| **API 통합** | `SnippetDetailReadTest` | 3 | GET /snippets/<pk>/ |
| **API 통합** | `SnippetDetailWriteTest` | 8 | PATCH/PUT/DELETE 권한 매트릭스 |

**디버깅 원칙**: 단위 테스트가 통과하는데 통합이 실패하면 로직은 무죄 — 통합 환경 설정(View · URL · Permission 등록)을 의심.

---

## API 엔드포인트

| 메서드 | 경로 | 동작 | 인증 |
|--------|------|------|------|
| `GET` | `/snippets/` | 목록 조회 | 불필요 |
| `POST` | `/snippets/` | 생성 | **필수** |
| `GET` | `/snippets/<pk>/` | 단일 조회 | 불필요 |
| `PUT` / `PATCH` | `/snippets/<pk>/` | 수정 | **소유자만** |
| `DELETE` | `/snippets/<pk>/` | 삭제 | **소유자만** |

---

## 보안 시나리오 검증

이 저장소는 다음 공격 시나리오를 단위 테스트로 막아냅니다.

| 공격 시나리오 | 방어 메커니즘 | 검증 테스트 |
|------------|-------------|------------|
| 익명 사용자가 글 작성 시도 | `IsAuthenticatedOrReadOnly` | `test_anonymous_cannot_create` |
| `owner=other_user`로 위조 전송 | `ReadOnlyField` + `perform_create` | `test_client_cannot_forge_owner_via_request_body` |
| 비소유자가 타인 글 수정/삭제 | `IsOwnerOrReadOnly.has_object_permission` | `test_non_owner_cannot_patch`, `test_non_owner_cannot_delete` |
| 소유자가 PATCH로 소유권 양도 시도 | `ReadOnlyField` (UPDATE에서도 작동) | `test_patch_cannot_change_owner_even_by_owner` |

---

## 강의 자료

이 저장소와 짝을 이루는 슬라이드 자료입니다.

| 자료 | 분량 | 내용 |
|------|:---:|------|
| `DRF_GenericAPIView_Mixin.pptx` | 17장 | 개념 · 패턴 · 책임 분리 · 테스트 전략 |
| `DRF_Test_Walkthrough.pptx` | 11장 | 30개 테스트 메서드별 walkthrough |

### 권장 학습 순서

1. 메인 PPT **1~13장** — 개념 학습
2. 본 저장소 코드 직접 작성
3. `python manage.py test snippets` — 30개 테스트 통과 확인
4. 메인 PPT **14~17장** — 테스트 전략 정리
5. Walkthrough PPT — 디버깅 reference card로 활용

---

## 자주 발생하는 문제

| 증상 | 원인 | 해결 |
|------|------|------|
| `NoReverseMatch: 'snippet-list' not found` | `urls.py`에 `name=` 누락 | `path(..., name='snippet-list')` 추가 |
| POST 시 `owner` 필드 NULL 오류 | `perform_create` 누락 | `View.perform_create()` 오버라이드 |
| 비소유자가 수정 가능 | `permission_classes` 누락 | `[IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]` 등록 |
| 입력에 `owner='bob'`가 통과됨 | `ReadOnlyField` 미선언 | Serializer에 `owner = serializers.ReadOnlyField(...)` 추가 |

---

## 라이센스 및 저작권

본 자료는 **강의·학습 목적**으로 작성되었습니다. 학습 외 용도로 사용 시 출처를 표기해 주시기 바랍니다.

- 강의: 풀스택서비스컴퓨팅
- 소속: 국민대학교 소프트웨어융합대학 소프트웨어학부
- 담당: 김상철 교수 (Prof. Sang-Chul Kim)

---

## 참고 자료

- [DRF 공식 튜토리얼 4 — 인증과 권한](https://www.django-rest-framework.org/tutorial/4-authentication-and-permissions/)
- [Django 공식 문서](https://docs.djangoproject.com/)
- [DRF 공식 문서](https://www.django-rest-framework.org/)
