from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q, Count, Exists, OuterRef, Prefetch
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import *
from .serializers import *

User = get_user_model()

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
    
    def retrieve(self, request, *args, **kwargs):
        post = self.get_object()
        
        PostView.objects.get_or_create(user=request.user, post=post)
        
        return super().retrieve(request, *args, **kwargs)
    
    @action(detail=False, methods=['get'])
    def news_feed(self, request):
        """
        Optimized news feed showing:
        1. Posts from followed users (prioritized, unseen first)
        2. Top engaged posts from others (excluding already viewed)
        """
        user = request.user
        
        # Get users that current user follows
        following_ids = Follow.objects.filter(follower=user).values_list('following_id', flat=True)
        
        # Get posts already viewed by user
        viewed_post_ids = PostView.objects.filter(user=user).values_list('post_id', flat=True)
        
        # Posts from followed users (unseen first, then seen)
        followed_posts_unseen = Post.objects.filter(
            user_id__in=following_ids,
            status='approved'
        ).exclude(
            id__in=viewed_post_ids
        ).select_related('user').prefetch_related(
            'likes', 'comments', 'shares'
        ).order_by('-created_at')
        
        followed_posts_seen = Post.objects.filter(
            user_id__in=following_ids,
            status='approved',
            id__in=viewed_post_ids
        ).select_related('user').prefetch_related(
            'likes', 'comments', 'shares'
        ).order_by('-created_at')
        
        # Top engaged posts from non-followed users (excluding viewed)
        # Calculate engagement within last 7 days for relevancy
        recent_date = timezone.now() - timedelta(days=7)
        
        top_engaged_posts = Post.objects.filter(
            status='approved'
        ).exclude(
            user_id__in=following_ids
        ).exclude(
            user=user
        ).exclude(
            id__in=viewed_post_ids
        ).annotate(
            engagement=Count('likes') + Count('comments') * 2 + Count('shares') * 3
        ).filter(
            created_at__gte=recent_date
        ).select_related('user').prefetch_related(
            'likes', 'comments', 'shares'
        ).order_by('-engagement', '-created_at')
        
        # Combine querysets: followed unseen -> followed seen -> top engaged
        # Limit to reasonable numbers for performance
        followed_unseen_list = list(followed_posts_unseen[:20])
        followed_seen_list = list(followed_posts_seen[:10])
        top_engaged_list = list(top_engaged_posts[:10])
        
        combined_posts = followed_unseen_list + followed_seen_list + top_engaged_list
        
        # Paginate the combined results
        page = self.paginate_queryset(combined_posts)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(combined_posts, many=True)
        return Response(serializer.data)


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
    
    @action(detail=False, methods=['get'])
    def user_posts(self, request):
        """Get approved posts by a specific user (via query param ?user_id=X)"""
        user_id = request.query_params.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        posts = Post.objects.filter(
            user_id=user_id,
            status='approved'
        ).select_related('user').prefetch_related(
            'likes', 'comments', 'shares'
        ).order_by('-created_at')
        
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
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

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

class FollowViewSet(viewsets.ModelViewSet):
    queryset = Follow.objects.all()
    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        """Get followers or following based on query params"""
        queryset = Follow.objects.all()
        user_id = self.request.query_params.get('user_id')
        
        if self.request.query_params.get('followers') == 'true':
            # Get followers of a user
            if user_id:
                queryset = queryset.filter(following_id=user_id)
            else:
                queryset = queryset.filter(following=self.request.user)
        elif self.request.query_params.get('following') == 'true':
            # Get users that a user is following
            if user_id:
                queryset = queryset.filter(follower_id=user_id)
            else:
                queryset = queryset.filter(follower=self.request.user)
        elif self.action == 'list':
            # Default: show who current user is following
            queryset = queryset.filter(follower=self.request.user)
        
        return queryset.select_related('follower', 'following').order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(follower=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """Only the follower can unfollow"""
        follow = self.get_object()
        if follow.follower != request.user:
            raise PermissionDenied("You do not have permission to delete this follow.")
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['post'])
    def toggle_follow(self, request):
        """Toggle follow/unfollow for a user"""
        following_id = request.data.get('following_id')
        
        if not following_id:
            return Response(
                {'error': 'following_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            following_user = User.objects.get(id=following_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if following_user == request.user:
            return Response(
                {'error': 'You cannot follow yourself'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        follow = Follow.objects.filter(
            follower=request.user,
            following=following_user
        ).first()
        
        if follow:
            # Unfollow
            follow.delete()
            return Response(
                {'status': 'unfollowed', 'following': False},
                status=status.HTTP_200_OK
            )
        else:
            # Follow
            Follow.objects.create(
                follower=request.user,
                following=following_user
            )
            # Create notification
            Notification.objects.create(
                recipient=following_user,
                sender=request.user,
                notification_type='follow'
            )
            return Response(
                {'status': 'followed', 'following': True},
                status=status.HTTP_201_CREATED
            )

    @action(detail=False, methods=['get'])
    def user_profile(self, request):
        """Get user profile with follow statistics"""
        user_id = request.query_params.get('user_id')
        
        if not user_id:
            # Get current user's profile
            target_user = request.user
        else:
            try:
                target_user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Get stats with optimized queries
        followers_count = Follow.objects.filter(following=target_user).count()
        following_count = Follow.objects.filter(follower=target_user).count()
        posts_count = Post.objects.filter(user=target_user, status='approved').count()
        
        # Check if current user is following this user
        is_following = False
        if request.user != target_user:
            is_following = Follow.objects.filter(
                follower=request.user,
                following=target_user
            ).exists()
        
        profile_data = {
            'user_id': target_user.id,
            'username': target_user.username,
            'followers_count': followers_count,
            'following_count': following_count,
            'posts_count': posts_count,
            'is_following': is_following
        }
        
        serializer = UserProfileSerializer(profile_data)
        return Response(serializer.data)


# NEW ADDED - Notification ViewSet
class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        """Get notifications for current user"""
        return Notification.objects.filter(
            recipient=self.request.user
        ).select_related('sender', 'post', 'comment').order_by('-created_at')

    @action(detail=False, methods=['get'])
    def unread(self, request):
        """Get unread notifications only"""
        notifications = self.get_queryset().filter(is_read=False)
        page = self.paginate_queryset(notifications)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(notifications, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get count of unread notifications"""
        count = self.get_queryset().filter(is_read=False).count()
        return Response({'unread_count': count})

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read"""
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({
            'status': 'success',
            'marked_read': updated
        })

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a single notification as read"""
        notification = self.get_object()
        if notification.recipient != request.user:
            raise PermissionDenied("You do not have permission to modify this notification.")
        
        notification.is_read = True
        notification.save()
        
        serializer = self.get_serializer(notification)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """Only the recipient can delete their notification"""
        notification = self.get_object()
        if notification.recipient != request.user:
            raise PermissionDenied("You do not have permission to delete this notification.")
        return super().destroy(request, *args, **kwargs)