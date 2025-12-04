from rest_framework.routers import DefaultRouter
from django.urls import path, include
from interest.views import *
from post.views import *
from chats.views import *
from marketplace.views import *
from community.views import *

router = DefaultRouter()

""" User Interest Section """
router.register("categories", CategoryViewSet, basename="category")
router.register("subcategories", SubCategoryViewSet, basename="subcategory")

""" Post Section """
router.register(r'posts', PostViewSet, basename='post')
router.register(r'likes', LikeViewSet, basename='like')
router.register(r'comments', CommentViewSet, basename='comment')
router.register(r'shares', ShareViewSet, basename='share')
router.register(r'follows', FollowViewSet, basename='follow')
router.register(r'notifications', NotificationViewSet, basename='notification')

""" Marketplace Section """
router.register(r'marketplace/categories', MarketplaceCategoryViewSet, basename="marketplace-category")
router.register(r'marketplace/subcategories', MarketplaceSubCategoryViewSet, basename="marketplace-subcategory")
router.register(r'marketplace/items', MarketplaceProductViewSet, basename="marketplace-item")

""" Community Section """
router.register(r'communities', CommunityViewSet, basename='community')
router.register(r'join-requests', CommunityJoinRequestViewSet, basename='join-request')

""" Chat Section """
# router.register(r'chat/rooms', RoomViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
