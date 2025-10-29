# urls.py
from rest_framework.routers import DefaultRouter
from django.urls import path, include
from interest.views import *
from post.views import *

router = DefaultRouter()
""" User Interest Section """
router.register("categories", CategoryViewSet, basename="category")
router.register("subcategories", SubCategoryViewSet, basename="subcategory")
router.register("interests", UserInterestViewSet, basename="interest")

""" Post Section """
router.register(r'posts', PostViewSet, basename='post')
router.register(r'likes', LikeViewSet, basename='like')
router.register(r'comments', CommentViewSet, basename='comment')
router.register(r'shares', ShareViewSet, basename='share')
router.register(r'follows', FollowViewSet, basename='follow')
router.register(r'notifications', NotificationViewSet, basename='notification') 

urlpatterns = [
    path("", include(router.urls)),
]
