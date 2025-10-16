from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q
from .models import Post, Like, Comment, Share
from .serializers import PostSerializer, LikeSerializer, CommentSerializer, ShareSerializer


class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all().order_by('-created_at')
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if self.action == 'list':
            return Post.objects.filter(status='approved').order_by('-created_at')
        else:
            return Post.objects.filter(
                Q(status='approved') | Q(user=user)
            ).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def update(self, request, *args, **kwargs):
        """Only the post owner can update their post."""
        post = self.get_object()
        if post.user != request.user:
            raise PermissionDenied("You do not have permission to edit this post.")
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """Only the post owner can partially update their post."""
        post = self.get_object()
        if post.user != request.user:
            raise PermissionDenied("You do not have permission to edit this post.")
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Only the post owner can delete their post."""
        post = self.get_object()
        if post.user != request.user:
            raise PermissionDenied("You do not have permission to delete this post.")
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def profile_posts(self, request):
        """Get all posts created by the current user (any status)"""
        posts = Post.objects.filter(user=request.user, status='approved').order_by('-created_at')
        page = self.paginate_queryset(posts)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(posts, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_posts(self, request):
        """Get all posts created by the current user (any status)"""
        posts = Post.objects.filter(user=request.user).order_by('-created_at')
        page = self.paginate_queryset(posts)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(posts, many=True)
        return Response(serializer.data)


class LikeViewSet(viewsets.ModelViewSet):
    queryset = Like.objects.all()
    serializer_class = LikeSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        """Filter likes based on query params or show user's likes"""
        queryset = Like.objects.all()
        post_id = self.request.query_params.get('post', None)
        if post_id:
            queryset = queryset.filter(post_id=post_id)
        elif self.action == 'list':
            queryset = queryset.filter(user=self.request.user)
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """Only the like owner can delete their like (unlike)."""
        like = self.get_object()
        if like.user != request.user:
            raise PermissionDenied("You do not have permission to delete this like.")
        return super().destroy(request, *args, **kwargs)


class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Optionally filter comments by post"""
        queryset = Comment.objects.all()
        post_id = self.request.query_params.get('post', None)
        parent_id = self.request.query_params.get('parent', None)
        
        if post_id:
            queryset = queryset.filter(post_id=post_id)
        if parent_id:
            queryset = queryset.filter(parent_id=parent_id)
        
        return queryset.order_by('created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def update(self, request, *args, **kwargs):
        """Only the comment author can update their comment."""
        comment = self.get_object()
        if comment.user != request.user:
            raise PermissionDenied("You do not have permission to edit this comment.")
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """Only the comment author can partially update their comment."""
        comment = self.get_object()
        if comment.user != request.user:
            raise PermissionDenied("You do not have permission to edit this comment.")
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Comment author or post owner can delete the comment.
        Deleting a root comment will cascade delete all nested replies (Django's CASCADE).
        """
        comment = self.get_object()
        post_owner = comment.post.user
        
        if comment.user != request.user and post_owner != request.user:
            raise PermissionDenied("You do not have permission to delete this comment.")
        
        # Django will automatically cascade delete all replies due to on_delete=CASCADE
        return super().destroy(request, *args, **kwargs)


class ShareViewSet(viewsets.ModelViewSet):
    queryset = Share.objects.all()
    serializer_class = ShareSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']  # No PUT/PATCH

    def get_queryset(self):
        """Filter shares based on query params or show user's shares"""
        queryset = Share.objects.all()
        post_id = self.request.query_params.get('post', None)
        if post_id:
            queryset = queryset.filter(post_id=post_id)
        elif self.action == 'list':
            queryset = queryset.filter(user=self.request.user)
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """Only the share owner can delete their share."""
        share = self.get_object()
        if share.user != request.user:
            raise PermissionDenied("You do not have permission to delete this share.")
        return super().destroy(request, *args, **kwargs)