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
from django.core.files.storage import default_storage
from rest_framework import parsers
from community.models import *
from community.serializers import *

User = get_user_model()

""" Viewset for Posts """
class PostViewSet(viewsets.ModelViewSet):
    """Enhanced PostViewSet with community integration"""
    queryset = Post.objects.all().order_by('-created_at')
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def get_queryset(self):
        user = self.request.user
        if self.action == 'list':
            # Show approved posts (both personal and community)
            return Post.objects.filter(status='approved').order_by('-created_at')
        else:
            return Post.objects.filter(
                Q(status='approved') | Q(user=user)
            ).order_by('-created_at')

    def perform_create(self, serializer):
        """Create post with community validation"""
        community = serializer.validated_data.get('community')
        
        # If posting to a community, verify membership
        if community:
            membership = CommunityMember.objects.filter(
                user=self.request.user,
                community=community,
                is_approved=True
            ).first()
            
            if not membership:
                raise PermissionDenied("You must be a member to post in this community.")
            
            # Check if community requires approval for posts
            if community.visibility == 'private':
                serializer.save(user=self.request.user, status='pending')
            else:
                serializer.save(user=self.request.user)
        else:
            serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response({
            "success": True,
            "message": "Post created successfully",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=False, methods=['get'])
    def news_feed(self, request):
        """
        Enhanced news feed showing:
        1. Posts from followed users (personal posts)
        2. Posts from joined communities
        3. Top engaged posts from popular communities (for discovery)
        4. Top engaged posts from non-followed users
        
        Priority: Unseen followed content > Community content > Discovery content
        """
        user = request.user
        
        # Get users that current user follows
        following_ids = Follow.objects.filter(follower=user).values_list('following_id', flat=True)
        
        # Get communities user is member of
        joined_community_ids = CommunityMember.objects.filter(
            user=user,
            is_approved=True
        ).values_list('community_id', flat=True)
        
        # Get posts already viewed by user
        viewed_post_ids = PostView.objects.filter(user=user).values_list('post_id', flat=True)
        
        # 1. Personal posts from followed users (unseen first)
        followed_posts_unseen = Post.objects.filter(
            user_id__in=following_ids,
            status='approved',
            community__isnull=True  # Only personal posts
        ).exclude(
            id__in=viewed_post_ids
        ).select_related('user').prefetch_related(
            'likes', 'comments', 'shares'
        ).order_by('-created_at')
        
        # 2. Posts from joined communities (unseen first, pinned at top)
        community_posts_unseen = Post.objects.filter(
            community_id__in=joined_community_ids,
            status='approved'
        ).exclude(
            id__in=viewed_post_ids
        ).select_related('user', 'community').prefetch_related(
            'likes', 'comments', 'shares'
        ).order_by('-is_pinned', '-created_at')
        
        # 3. Top posts from popular communities (for discovery)
        recent_date = timezone.now() - timedelta(days=7)
        popular_community_ids = Community.objects.filter(
            visibility='public'
        ).exclude(
            id__in=joined_community_ids
        ).order_by('-members_count')[:20].values_list('id', flat=True)
        
        popular_community_posts = Post.objects.filter(
            community_id__in=popular_community_ids,
            status='approved',
            created_at__gte=recent_date
        ).exclude(
            id__in=viewed_post_ids
        ).annotate(
            engagement=Count('likes') + Count('comments') * 2 + Count('shares') * 3
        ).select_related('user', 'community').prefetch_related(
            'likes', 'comments', 'shares'
        ).order_by('-engagement', '-created_at')
        
        # 4. Top engaged personal posts from non-followed users
        top_personal_posts = Post.objects.filter(
            status='approved',
            community__isnull=True,
            created_at__gte=recent_date
        ).exclude(
            user_id__in=following_ids
        ).exclude(
            user=user
        ).exclude(
            id__in=viewed_post_ids
        ).annotate(
            engagement=Count('likes') + Count('comments') * 2 + Count('shares') * 3
        ).select_related('user').prefetch_related(
            'likes', 'comments', 'shares'
        ).order_by('-engagement', '-created_at')
        
        # 5. Seen posts from followed users and communities (lower priority)
        followed_posts_seen = Post.objects.filter(
            Q(user_id__in=following_ids, community__isnull=True) |
            Q(community_id__in=joined_community_ids),
            status='approved',
            id__in=viewed_post_ids
        ).select_related('user', 'community').prefetch_related(
            'likes', 'comments', 'shares'
        ).order_by('-created_at')
        
        # Combine in priority order
        followed_unseen_list = list(followed_posts_unseen[:15])
        community_unseen_list = list(community_posts_unseen[:15])
        popular_community_list = list(popular_community_posts[:10])
        top_personal_list = list(top_personal_posts[:10])
        followed_seen_list = list(followed_posts_seen[:10])
        
        combined_posts = (
            followed_unseen_list + 
            community_unseen_list + 
            popular_community_list + 
            top_personal_list + 
            followed_seen_list
        )
        
        # Paginate the combined results
        page = self.paginate_queryset(combined_posts)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "success": True,
                "message": "News feed retrieved successfully",
                "data": serializer.data
            })
        
        serializer = self.get_serializer(combined_posts, many=True)
        return Response({
            "success": True,
            "message": "News feed retrieved successfully",
            "data": serializer.data
        })

    @action(detail=False, methods=['get'])
    def community_posts(self, request):
        """Get posts from a specific community"""
        community_name = request.query_params.get('community')
        
        if not community_name:
            return Response({
                "success": False,
                "error": "community parameter is required"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            community = Community.objects.get(name=community_name)
        except Community.DoesNotExist:
            return Response({
                "success": False,
                "error": "Community not found"
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user can view posts
        if community.visibility == 'private':
            membership = CommunityMember.objects.filter(
                user=request.user,
                community=community,
                is_approved=True
            ).first()
            
            if not membership:
                return Response({
                    "success": False,
                    "error": "You must be a member to view posts in this private community"
                }, status=status.HTTP_403_FORBIDDEN)
        
        posts = Post.objects.filter(
            community=community,
            status='approved'
        ).select_related('user', 'community').prefetch_related(
            'likes', 'comments', 'shares'
        ).order_by('-is_pinned', '-created_at')
        
        page = self.paginate_queryset(posts)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "success": True,
                "message": "Community posts retrieved successfully",
                "data": serializer.data
            })
        
        serializer = self.get_serializer(posts, many=True)
        return Response({
            "success": True,
            "message": "Community posts retrieved successfully",
            "data": serializer.data
        })

    @action(detail=True, methods=['post'])
    def pin(self, request, pk=None):
        """Pin a post in a community (moderators/admins only)"""
        post = self.get_object()
        
        if not post.community:
            return Response({
                "success": False,
                "error": "Only community posts can be pinned"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user can manage community
        membership = CommunityMember.objects.filter(
            user=request.user,
            community=post.community,
            is_approved=True
        ).first()
        
        if not (membership and membership.role in ['admin', 'moderator']):
            raise PermissionDenied("You do not have permission to pin posts.")
        
        post.is_pinned = True
        post.save()
        
        return Response({
            "success": True,
            "message": "Post pinned successfully",
            "data": self.get_serializer(post).data
        })

    @action(detail=True, methods=['post'])
    def unpin(self, request, pk=None):
        """Unpin a post"""
        post = self.get_object()
        
        if not post.community:
            return Response({
                "success": False,
                "error": "Only community posts can be unpinned"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user can manage community
        membership = CommunityMember.objects.filter(
            user=request.user,
            community=post.community,
            is_approved=True
        ).first()
        
        if not (membership and membership.role in ['admin', 'moderator']):
            raise PermissionDenied("You do not have permission to unpin posts.")
        
        post.is_pinned = False
        post.save()
        
        return Response({
            "success": True,
            "message": "Post unpinned successfully",
            "data": self.get_serializer(post).data
        })

    @action(detail=False, methods=['get'])
    def profile_posts(self, request):
        """Get approved posts created by current user (both personal and community)"""
        posts = Post.objects.filter(
            user=request.user, 
            status='approved'
        ).select_related('community').order_by('-created_at')
        
        page = self.paginate_queryset(posts)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "success": True,
                "message": "Profile posts retrieved successfully",
                "data": serializer.data
            })
        serializer = self.get_serializer(posts, many=True)
        return Response({
            "success": True,
            "message": "Profile posts retrieved successfully",
            "data": serializer.data
        })

    @action(detail=False, methods=['get'])
    def my_posts(self, request):
        """Get all posts created by current user (any status)"""
        posts = Post.objects.filter(user=request.user).select_related('community').order_by('-created_at')
        page = self.paginate_queryset(posts)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "success": True,
                "message": "My posts retrieved successfully",
                "data": serializer.data
            })
        serializer = self.get_serializer(posts, many=True)
        return Response({
            "success": True,
            "message": "My posts retrieved successfully",
            "data": serializer.data
        })

    @action(detail=False, methods=['get'])
    def user_posts(self, request):
        """Get approved posts by a specific user"""
        user_id = request.query_params.get('user_id')
        
        if not user_id:
            return Response({
                "success": False,
                "error": "user_id parameter is required"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        posts = Post.objects.filter(
            user_id=user_id,
            status='approved'
        ).select_related('user', 'community').prefetch_related(
            'likes', 'comments', 'shares'
        ).order_by('-created_at')
        
        page = self.paginate_queryset(posts)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "success": True,
                "message": "User posts retrieved successfully",
                "data": serializer.data
            })
        
        serializer = self.get_serializer(posts, many=True)
        return Response({
            "success": True,
            "message": "User posts retrieved successfully",
            "data": serializer.data
        })

class LikeViewSet(viewsets.ModelViewSet):
    """ Viewset for Like """
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

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response({
            "success": True,
            "message": "Post liked successfully",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "success": True,
                "message": "Likes retrieved successfully",
                "data": serializer.data
            })
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "success": True,
            "message": "Likes retrieved successfully",
            "data": serializer.data
        })

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "success": True,
            "message": "Like retrieved successfully",
            "data": serializer.data
        })

    def destroy(self, request, *args, **kwargs):
        """Only the like owner can delete their like (unlike)."""
        like = self.get_object()
        if like.user != request.user:
            raise PermissionDenied("You do not have permission to delete this like.")
        self.perform_destroy(like)
        return Response({
            "success": True,
            "message": "Post unliked successfully",
            "data": None
        }, status=status.HTTP_200_OK)


class CommentViewSet(viewsets.ModelViewSet):
    """ Viewset for Comment """
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

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response({
            "success": True,
            "message": "Comment created successfully",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "success": True,
                "message": "Comments retrieved successfully",
                "data": serializer.data
            })
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "success": True,
            "message": "Comments retrieved successfully",
            "data": serializer.data
        })

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "success": True,
            "message": "Comment retrieved successfully",
            "data": serializer.data
        })

    def update(self, request, *args, **kwargs):
        """Only the comment author can update their comment."""
        comment = self.get_object()
        if comment.user != request.user:
            raise PermissionDenied("You do not have permission to edit this comment.")
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(comment, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            "success": True,
            "message": "Comment updated successfully",
            "data": serializer.data
        })

    def partial_update(self, request, *args, **kwargs):
        """Only the comment author can partially update their comment."""
        comment = self.get_object()
        if comment.user != request.user:
            raise PermissionDenied("You do not have permission to edit this comment.")
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

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
        self.perform_destroy(comment)
        return Response({
            "success": True,
            "message": "Comment deleted successfully",
            "data": None
        }, status=status.HTTP_200_OK)


class ShareViewSet(viewsets.ModelViewSet):
    """ Viewset for Share """
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

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response({
            "success": True,
            "message": "Post shared successfully",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "success": True,
                "message": "Shares retrieved successfully",
                "data": serializer.data
            })
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "success": True,
            "message": "Shares retrieved successfully",
            "data": serializer.data
        })

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "success": True,
            "message": "Share retrieved successfully",
            "data": serializer.data
        })

    def destroy(self, request, *args, **kwargs):
        """Only the share owner can delete their share."""
        share = self.get_object()
        if share.user != request.user:
            raise PermissionDenied("You do not have permission to delete this share.")
        self.perform_destroy(share)
        return Response({
            "success": True,
            "message": "Share removed successfully",
            "data": None
        }, status=status.HTTP_200_OK)

class FollowViewSet(viewsets.ModelViewSet):
    """ Viewset for Follow """
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

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response({
            "success": True,
            "message": "User followed successfully",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "success": True,
                "message": "Follows retrieved successfully",
                "data": serializer.data
            })
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "success": True,
            "message": "Follows retrieved successfully",
            "data": serializer.data
        })

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "success": True,
            "message": "Follow retrieved successfully",
            "data": serializer.data
        })

    def destroy(self, request, *args, **kwargs):
        """Only the follower can unfollow"""
        follow = self.get_object()
        if follow.follower != request.user:
            raise PermissionDenied("You do not have permission to delete this follow.")
        self.perform_destroy(follow)
        return Response({
            "success": True,
            "message": "User unfollowed successfully",
            "data": None
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def toggle_follow(self, request):
        """Toggle follow/unfollow for a user"""
        following_id = request.data.get('following_id')
        
        if not following_id:
            return Response({
                "success": False,
                "error": "following_id is required"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            following_user = User.objects.get(id=following_id)
        except User.DoesNotExist:
            return Response({
                "success": False,
                "error": "User not found"
            }, status=status.HTTP_404_NOT_FOUND)
        
        if following_user == request.user:
            return Response({
                "success": False,
                "error": "You cannot follow yourself"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        follow = Follow.objects.filter(
            follower=request.user,
            following=following_user
        ).first()
        
        if follow:
            # Unfollow
            follow.delete()
            return Response({
                "success": True,
                "message": "User unfollowed successfully",
                "data": {'status': 'unfollowed', 'following': False}
            }, status=status.HTTP_200_OK)
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
            return Response({
                "success": True,
                "message": "User followed successfully",
                "data": {'status': 'followed', 'following': True}
            }, status=status.HTTP_201_CREATED)

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
                return Response({
                    "success": False,
                    "error": "User not found"
                }, status=status.HTTP_404_NOT_FOUND)
        
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
        return Response({
            "success": True,
            "message": "User profile retrieved successfully",
            "data": serializer.data
        })
class NotificationViewSet(viewsets.ModelViewSet):
    """ Viewset for Notification """
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']
    
    def get_queryset(self):
        """Get notifications for current user"""
        return Notification.objects.filter(
            recipient=self.request.user
        ).select_related('sender', 'post', 'comment').order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        """Get all notifications for current user"""
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "success": True,
                "message": "Notifications retrieved successfully",
                "data": serializer.data
            })
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "success": True,
            "message": "Notifications retrieved successfully",
            "data": serializer.data
        })
    
    def retrieve(self, request, *args, **kwargs):
        """Get a single notification"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "success": True,
            "message": "Notification retrieved successfully",
            "data": serializer.data
        })
    
    def partial_update(self, request, *args, **kwargs):
        """Partially update a notification"""
        instance = self.get_object()
        if instance.recipient != request.user:
            return Response({
                "success": False,
                "error": "You do not have permission to modify this notification."
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            "success": True,
            "message": "Notification updated successfully",
            "data": serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def unread(self, request):
        """Get unread notifications only"""
        notifications = self.get_queryset().filter(is_read=False)
        page = self.paginate_queryset(notifications)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "success": True,
                "message": "Unread notifications retrieved successfully",
                "data": serializer.data
            })
        
        serializer = self.get_serializer(notifications, many=True)
        return Response({
            "success": True,
            "message": "Unread notifications retrieved successfully",
            "data": serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get count of unread notifications"""
        count = self.get_queryset().filter(is_read=False).count()
        return Response({
            "success": True,
            "message": "Unread count retrieved successfully",
            "data": {'unread_count': count}
        })
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read"""
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({
            "success": True,
            "message": "All notifications marked as read",
            "data": {
                'status': 'success',
                'marked_read': updated
            }
        })
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark a single notification as read"""
        notification = self.get_object()
        if notification.recipient != request.user:
            return Response({
                "success": False,
                "error": "You do not have permission to modify this notification."
            }, status=status.HTTP_403_FORBIDDEN)
        
        notification.is_read = True
        notification.save()
        
        serializer = self.get_serializer(notification)
        return Response({
            "success": True,
            "message": "Notification marked as read",
            "data": serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        """Only the recipient can delete their notification"""
        notification = self.get_object()
        if notification.recipient != request.user:
            return Response({
                "success": False,
                "error": "You do not have permission to delete this notification."
            }, status=status.HTTP_403_FORBIDDEN)
        
        super().destroy(request, *args, **kwargs)
        return Response({
            "success": True,
            "message": "Notification deleted successfully",
            "data": None
        }, status=status.HTTP_200_OK)
    
""" End of Viewset for Posts """