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
router.register('posts', PostViewSet, basename='post')
router.register('likes', LikeViewSet, basename='like')
router.register('comments', CommentViewSet, basename='comment')
router.register('shares', ShareViewSet, basename='share')

urlpatterns = [
    path("", include(router.urls)),
]
