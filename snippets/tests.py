"""
==============================================================
Snippet API 종합 테스트  ─  풀스택서비스컴퓨팅 강의용
==============================================================
DRF 튜토리얼 패턴 전 범위 검증:
  · GenericAPIView + Mixin 조합
  · perform_create(owner=request.user)  ← 슬라이드 11~13
  · IsOwnerOrReadOnly 권한               ← 슬라이드 15~17 (예정)
  · ReadOnlyField로 owner 위조 차단

전제하는 코드 구조:
  snippets/
    models.py        # Snippet(title, code, linenos, language, style, owner)
    serializers.py   # SnippetSerializer (owner = ReadOnlyField)
    permissions.py   # IsOwnerOrReadOnly
    views.py         # SnippetList (ListCreateAPIView),
                     # SnippetDetail (RetrieveUpdateDestroyAPIView)
    urls.py          # name='snippet-list', name='snippet-detail'

실행:
  python manage.py test snippets.tests.test_snippets -v 2

추가 도구:
  pip install coverage
  coverage run --source=snippets manage.py test snippets
  coverage report -m
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse, NoReverseMatch

from rest_framework import status
from rest_framework.test import (
    APITestCase, APIRequestFactory,
)

from snippets.models import Snippet
from snippets.serializers import SnippetSerializer
from snippets.permissions import IsOwnerOrReadOnly


User = get_user_model()


# ------------------------------------------------------------------
# URL 헬퍼 ─ snippets/urls.py 에 name= 인자가 있으면 reverse() 사용,
#           없으면 하드코딩된 경로로 폴백 (강의용으로 양쪽 모두 지원)
#
# 모범 사례는 urls.py 에 다음과 같이 name 을 부여하는 것:
#   path('snippets/',           views.SnippetList.as_view(),
#        name='snippet-list')
#   path('snippets/<int:pk>/',  views.SnippetDetail.as_view(),
#        name='snippet-detail')
# ------------------------------------------------------------------
def _list_url():
    try:
        return reverse('snippet-list')
    except NoReverseMatch:
        return '/snippets/'


def _detail_url(pk):
    try:
        return reverse('snippet-detail', args=[pk])
    except NoReverseMatch:
        return f'/snippets/{pk}/'


# ==================================================================
# 공통 베이스 ─ 두 명의 사용자와 각자 소유의 snippet 한 건씩
# ------------------------------------------------------------------
# setUpTestData 는 TestCase 단위로 한 번만 실행되어 setUp 보다 빠르다.
# 단, 각 테스트가 객체를 수정하면 다음 테스트에 영향을 줄 수 있으므로
# 수정/삭제 테스트에서는 refresh_from_db / 재조회로 격리한다.
# ==================================================================
class SnippetTestBase(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user(
            username='alice', password='alice_pw'
        )
        cls.bob = User.objects.create_user(
            username='bob', password='bob_pw'
        )
        cls.alice_snippet = Snippet.objects.create(
            title='alice 코드',
            code='print("alice")',
            owner=cls.alice,
        )
        cls.bob_snippet = Snippet.objects.create(
            title='bob 코드',
            code='print("bob")',
            owner=cls.bob,
        )

    @property
    def list_url(self):
        return _list_url()

    def detail_url(self, pk):
        return _detail_url(pk)


# ==================================================================
# 1) Serializer 레벨 ─ owner는 read-only로 노출 및 취급되는가
#    검증 대상: 슬라이드 12 "Serializer 컬럼"
# ==================================================================
class SnippetSerializerTest(SnippetTestBase):

    def test_owner_field_is_read_only(self):
        """ReadOnlyField 로 선언된 owner 는 read_only 속성이 True"""
        sz = SnippetSerializer()
        self.assertTrue(sz.fields['owner'].read_only)

    def test_owner_appears_in_serialized_output(self):
        """직렬화 결과에는 owner.username 이 포함된다"""
        data = SnippetSerializer(self.alice_snippet).data
        self.assertEqual(data['owner'], 'alice')

    def test_client_supplied_owner_is_silently_ignored(self):
        """공격자가 owner 를 보내도 validated_data 에 포함되지 않는다"""
        sz = SnippetSerializer(data={
            'title': '위조 시도',
            'code': 'evil',
            'owner': 'alice',          # ← 위조 시도
        })
        self.assertTrue(sz.is_valid(), sz.errors)
        self.assertNotIn('owner', sz.validated_data)


# ==================================================================
# 2) GET /snippets/  ─  누구든 목록 조회 가능 (SAFE_METHODS)
# ==================================================================
class SnippetListReadTest(SnippetTestBase):

    def test_anonymous_can_list(self):
        """익명 사용자도 SAFE_METHOD 로 목록 조회 200 OK"""
        res = self.client.get(self.list_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 2)

    def test_response_contains_owner_username(self):
        """응답 JSON 에 owner 가 사용자명으로 포함된다"""
        res = self.client.get(self.list_url)
        owners = {item['owner'] for item in res.data}
        self.assertEqual(owners, {'alice', 'bob'})


# ==================================================================
# 3) POST /snippets/  ─  생성 흐름 + perform_create 동작 검증
#    검증 대상: 슬라이드 11 흐름 ① get_serializer → ④ save(owner=...)
# ==================================================================
class SnippetCreateTest(SnippetTestBase):

    def test_anonymous_cannot_create(self):
        """IsAuthenticatedOrReadOnly 가 익명 POST 를 차단 (401 또는 403)"""
        res = self.client.post(self.list_url, {
            'title': 'x', 'code': 'print(1)',
        })
        self.assertIn(
            res.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )
        # 부가효과 없음 확인
        self.assertFalse(Snippet.objects.filter(title='x').exists())

    def test_authenticated_user_can_create(self):
        """로그인 사용자는 201 Created"""
        self.client.force_authenticate(user=self.alice)
        res = self.client.post(self.list_url, {
            'title': 'new', 'code': 'print(42)',
        })
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Snippet.objects.filter(title='new').exists())

    def test_perform_create_assigns_request_user_as_owner(self):
        """슬라이드 11 ④: serializer.save(owner=self.request.user)"""
        self.client.force_authenticate(user=self.alice)
        self.client.post(self.list_url, {
            'title': 'owned-by-alice', 'code': 'pass',
        })
        new_obj = Snippet.objects.get(title='owned-by-alice')
        self.assertEqual(new_obj.owner, self.alice)

    def test_client_cannot_forge_owner_via_request_body(self):
        """
        보안 시나리오: alice 로 로그인한 상태에서 body 에 owner='bob' 을 보냄.
        → ReadOnlyField 가 입력을 무시 → owner 는 여전히 alice 가 되어야 한다.
        """
        self.client.force_authenticate(user=self.alice)
        self.client.post(self.list_url, {
            'title': 'forged',
            'code': 'pass',
            'owner': 'bob',            # ← 위조 시도
        })
        new_obj = Snippet.objects.get(title='forged')
        self.assertEqual(new_obj.owner, self.alice)
        self.assertNotEqual(new_obj.owner, self.bob)

    def test_response_includes_owner_field(self):
        """201 Created 응답 body 에 owner 가 포함된다 (read 시에는 노출)"""
        self.client.force_authenticate(user=self.alice)
        res = self.client.post(self.list_url, {
            'title': 'visible', 'code': 'pass',
        })
        self.assertEqual(res.data['owner'], 'alice')


# ==================================================================
# 4) GET /snippets/<pk>/  ─  단일 조회는 누구든 허용
# ==================================================================
class SnippetDetailReadTest(SnippetTestBase):

    def test_anonymous_can_retrieve(self):
        res = self.client.get(self.detail_url(self.alice_snippet.pk))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['owner'], 'alice')

    def test_non_owner_can_retrieve(self):
        """비소유자도 SAFE_METHOD 로 조회 가능 (bob 이 alice 의 글 읽기)"""
        self.client.force_authenticate(user=self.bob)
        res = self.client.get(self.detail_url(self.alice_snippet.pk))
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_retrieve_404_for_missing_object(self):
        res = self.client.get(self.detail_url(99999))
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


# ==================================================================
# 5) PUT / PATCH / DELETE  ─  IsOwnerOrReadOnly 가 막아내는가
#    검증 대상: 슬라이드 15~17 예정 슬라이드의 "상황별 동작 결과 표"
# ==================================================================
class SnippetDetailWriteTest(SnippetTestBase):

    # ---------- 익명 사용자 ----------
    def test_anonymous_cannot_patch(self):
        res = self.client.patch(
            self.detail_url(self.alice_snippet.pk),
            {'title': 'hacked'},
        )
        self.assertIn(
            res.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_anonymous_cannot_delete(self):
        res = self.client.delete(self.detail_url(self.alice_snippet.pk))
        self.assertIn(
            res.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    # ---------- 비소유자 (인증되었지만 owner 아님) ----------
    def test_non_owner_cannot_patch(self):
        """bob 이 alice 의 글 수정 시도 → 403 + DB 변경 없음"""
        self.client.force_authenticate(user=self.bob)
        res = self.client.patch(
            self.detail_url(self.alice_snippet.pk),
            {'title': 'hacked'},
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.alice_snippet.refresh_from_db()
        self.assertEqual(self.alice_snippet.title, 'alice 코드')

    def test_non_owner_cannot_delete(self):
        self.client.force_authenticate(user=self.bob)
        res = self.client.delete(self.detail_url(self.alice_snippet.pk))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(
            Snippet.objects.filter(pk=self.alice_snippet.pk).exists()
        )

    # ---------- 소유자 ----------
    def test_owner_can_patch(self):
        self.client.force_authenticate(user=self.alice)
        res = self.client.patch(
            self.detail_url(self.alice_snippet.pk),
            {'title': '수정됨'},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.alice_snippet.refresh_from_db()
        self.assertEqual(self.alice_snippet.title, '수정됨')

    def test_owner_can_put_full(self):
        """PUT 은 전체 필드 필요 (PATCH 와 구분)"""
        self.client.force_authenticate(user=self.alice)
        res = self.client.put(
            self.detail_url(self.alice_snippet.pk),
            {'title': 'full-update', 'code': 'pass'},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_owner_can_delete(self):
        self.client.force_authenticate(user=self.alice)
        res = self.client.delete(self.detail_url(self.alice_snippet.pk))
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            Snippet.objects.filter(pk=self.alice_snippet.pk).exists()
        )

    def test_patch_cannot_change_owner_even_by_owner(self):
        """소유자라도 owner 필드 자체는 ReadOnlyField → 변경 불가"""
        self.client.force_authenticate(user=self.alice)
        self.client.patch(
            self.detail_url(self.alice_snippet.pk),
            {'owner': 'bob'},          # ← 소유권 양도 시도
        )
        self.alice_snippet.refresh_from_db()
        self.assertEqual(self.alice_snippet.owner, self.alice)


# ==================================================================
# 6) IsOwnerOrReadOnly 단위 테스트
#    has_object_permission() 을 직접 호출하여 4가지 시나리오 검증
#    뷰/URL 라우팅을 거치지 않으므로 권한 로직만 격리하여 본다
# ==================================================================
class IsOwnerOrReadOnlyUnitTest(SnippetTestBase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = IsOwnerOrReadOnly()

    def _make_request(self, method, user):
        """
        APIRequestFactory 가 만드는 request 에 user 만 수동 주입한다.
        has_object_permission 은 request.method 와 request.user 만 보므로 충분.
        """
        request = getattr(self.factory, method.lower())('/dummy/')
        request.user = user if user is not None else AnonymousUser()
        return request

    # ---- SAFE_METHODS 는 무조건 허용 ----
    def test_safe_method_by_anonymous_is_allowed(self):
        req = self._make_request('GET', user=None)
        self.assertTrue(
            self.permission.has_object_permission(
                req, view=None, obj=self.alice_snippet
            )
        )

    def test_safe_method_by_non_owner_is_allowed(self):
        req = self._make_request('GET', user=self.bob)
        self.assertTrue(
            self.permission.has_object_permission(
                req, view=None, obj=self.alice_snippet
            )
        )

    def test_safe_method_by_owner_is_allowed(self):
        req = self._make_request('GET', user=self.alice)
        self.assertTrue(
            self.permission.has_object_permission(
                req, view=None, obj=self.alice_snippet
            )
        )

    # ---- 쓰기 메서드는 owner 만 허용 ----
    def test_put_by_owner_is_allowed(self):
        req = self._make_request('PUT', user=self.alice)
        self.assertTrue(
            self.permission.has_object_permission(
                req, view=None, obj=self.alice_snippet
            )
        )

    def test_patch_by_owner_is_allowed(self):
        req = self._make_request('PATCH', user=self.alice)
        self.assertTrue(
            self.permission.has_object_permission(
                req, view=None, obj=self.alice_snippet
            )
        )

    def test_delete_by_owner_is_allowed(self):
        req = self._make_request('DELETE', user=self.alice)
        self.assertTrue(
            self.permission.has_object_permission(
                req, view=None, obj=self.alice_snippet
            )
        )

    def test_put_by_non_owner_is_denied(self):
        req = self._make_request('PUT', user=self.bob)
        self.assertFalse(
            self.permission.has_object_permission(
                req, view=None, obj=self.alice_snippet
            )
        )

    def test_delete_by_non_owner_is_denied(self):
        req = self._make_request('DELETE', user=self.bob)
        self.assertFalse(
            self.permission.has_object_permission(
                req, view=None, obj=self.alice_snippet
            )
        )

    def test_unsafe_method_by_anonymous_is_denied(self):
        """
        실제 운영에서는 IsAuthenticatedOrReadOnly 가 먼저 차단하지만
        IsOwnerOrReadOnly 자체로도 익명 쓰기를 거부하는지 단위 검증.
        """
        req = self._make_request('DELETE', user=None)
        self.assertFalse(
            self.permission.has_object_permission(
                req, view=None, obj=self.alice_snippet
            )
        )
