from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from django.db.models import Q, Count, Exists, OuterRef
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import *
from .serializers import *
from post.models import Notification

User = get_user_model()


class CommunityViewSet(viewsets.ModelViewSet):
    """ViewSet for Community management"""
    queryset = Community.objects.all()
    serializer_class = CommunitySerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = 'name'
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return CommunityDetailSerializer
        return CommunitySerializer
    
    def get_queryset(self):
        user = self.request.user
        
        if self.action == 'list':
            # Show public communities and communities user is member of
            return Community.objects.filter(
                Q(visibility='public') | Q(members__user=user, members__is_approved=True)
            ).distinct().annotate(
                user_is_member=Exists(
                    CommunityMember.objects.filter(
                        community=OuterRef('pk'),
                        user=user,
                        is_approved=True
                    )
                )
            ).order_by('-members_count', '-created_at')
        
        return Community.objects.all()
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response({
            "success": True,
            "message": "Community created successfully",
            "data": serializer.data
        }, status=status.HTTP_201_CREATED, headers=headers)
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "success": True,
                "message": "Communities retrieved successfully",
                "data": serializer.data
            })
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "success": True,
            "message": "Communities retrieved successfully",
            "data": serializer.data
        })
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response({
            "success": True,
            "message": "Community retrieved successfully",
            "data": serializer.data
        })
    
    def update(self, request, *args, **kwargs):
        community = self.get_object()
        
        # Check permissions
        if not self._can_manage_community(request.user, community):
            raise PermissionDenied("You do not have permission to edit this community.")
        
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(community, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            "success": True,
            "message": "Community updated successfully",
            "data": serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        community = self.get_object()
        
        # Only creator can delete
        if community.created_by != request.user:
            raise PermissionDenied("Only the community creator can delete it.")
        
        self.perform_destroy(community)
        return Response({
            "success": True,
            "message": "Community deleted successfully",
            "data": None
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Get popular communities based on members count"""
        communities = Community.objects.filter(
            visibility='public'
        ).order_by('-members_count', '-posts_count')[:20]
        
        page = self.paginate_queryset(communities)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "success": True,
                "message": "Popular communities retrieved successfully",
                "data": serializer.data
            })
        
        serializer = self.get_serializer(communities, many=True)
        return Response({
            "success": True,
            "message": "Popular communities retrieved successfully",
            "data": serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def my_communities(self, request):
        """Get communities the user is a member of"""
        communities = Community.objects.filter(
            members__user=request.user,
            members__is_approved=True
        ).distinct().order_by('-created_at')
        
        page = self.paginate_queryset(communities)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "success": True,
                "message": "Your communities retrieved successfully",
                "data": serializer.data
            })
        
        serializer = self.get_serializer(communities, many=True)
        return Response({
            "success": True,
            "message": "Your communities retrieved successfully",
            "data": serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def created_by_me(self, request):
        """Get communities created by the user"""
        communities = Community.objects.filter(
            created_by=request.user
        ).order_by('-created_at')
        
        page = self.paginate_queryset(communities)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "success": True,
                "message": "Communities you created retrieved successfully",
                "data": serializer.data
            })
        
        serializer = self.get_serializer(communities, many=True)
        return Response({
            "success": True,
            "message": "Communities you created retrieved successfully",
            "data": serializer.data
        })
    
    @action(detail=True, methods=['get'])
    def members(self, request, name=None):
        """Get all members of a community"""
        community = self.get_object()
        
        members = CommunityMember.objects.filter(
            community=community,
            is_approved=True
        ).select_related('user').order_by('-joined_at')
        
        page = self.paginate_queryset(members)
        if page is not None:
            serializer = CommunityMemberSerializer(page, many=True)
            return self.get_paginated_response({
                "success": True,
                "message": "Community members retrieved successfully",
                "data": serializer.data
            })
        
        serializer = CommunityMemberSerializer(members, many=True)
        return Response({
            "success": True,
            "message": "Community members retrieved successfully",
            "data": serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def join(self, request, name=None):
        """Join a community or request to join"""
        community = self.get_object()
        user = request.user
        
        # Check if already a member
        existing_member = CommunityMember.objects.filter(
            user=user,
            community=community
        ).first()
        
        if existing_member:
            if existing_member.is_approved:
                return Response({
                    "success": False,
                    "error": "You are already a member of this community"
                }, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({
                    "success": False,
                    "error": "Your membership is pending approval"
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Public communities: instant join
        if community.visibility == 'public':
            member = CommunityMember.objects.create(
                user=user,
                community=community,
                is_approved=True
            )
            
            return Response({
                "success": True,
                "message": "Successfully joined the community",
                "data": CommunityMemberSerializer(member).data
            }, status=status.HTTP_201_CREATED)
        
        # Restricted/Private: create join request
        else:
            join_request = CommunityJoinRequest.objects.create(
                user=user,
                community=community,
                message=request.data.get('message', '')
            )
            
            # Notify admins
            admins = CommunityMember.objects.filter(
                community=community,
                role__in=['admin', 'moderator'],
                is_approved=True
            ).select_related('user')
            
            for admin in admins:
                Notification.objects.create(
                    recipient=admin.user,
                    sender=user,
                    notification_type='community_join_request',
                    community=community,
                    message=f"wants to join {community.title}"
                )
            
            return Response({
                "success": True,
                "message": "Join request sent successfully",
                "data": CommunityJoinRequestSerializer(join_request).data
            }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def leave(self, request, name=None):
        """Leave a community"""
        community = self.get_object()
        user = request.user
        
        # Can't leave if you're the creator
        if community.created_by == user:
            return Response({
                "success": False,
                "error": "Community creator cannot leave. Transfer ownership or delete the community."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        member = CommunityMember.objects.filter(
            user=user,
            community=community
        ).first()
        
        if not member:
            return Response({
                "success": False,
                "error": "You are not a member of this community"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        member.delete()
        
        return Response({
            "success": True,
            "message": "Successfully left the community",
            "data": None
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def update_member_role(self, request, name=None):
        """Update a member's role (admin/moderator only)"""
        community = self.get_object()
        
        if not self._can_manage_community(request.user, community):
            raise PermissionDenied("You do not have permission to manage members.")
        
        user_id = request.data.get('user_id')
        new_role = request.data.get('role')
        
        if not user_id or not new_role:
            return Response({
                "success": False,
                "error": "user_id and role are required"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        member = CommunityMember.objects.filter(
            community=community,
            user_id=user_id
        ).first()
        
        if not member:
            return Response({
                "success": False,
                "error": "Member not found"
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Can't change creator's role
        if member.user == community.created_by:
            return Response({
                "success": False,
                "error": "Cannot change the creator's role"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        old_role = member.role
        member.role = new_role
        member.save()
        
        # Notify the member
        Notification.objects.create(
            recipient=member.user,
            sender=request.user,
            notification_type='community_role_changed',
            community=community,
            message=f"changed your role from {old_role} to {new_role} in {community.title}"
        )
        
        return Response({
            "success": True,
            "message": "Member role updated successfully",
            "data": CommunityMemberSerializer(member).data
        })
    
    @action(detail=True, methods=['post'])
    def remove_member(self, request, name=None):
        """Remove a member from the community"""
        community = self.get_object()
        
        if not self._can_manage_community(request.user, community):
            raise PermissionDenied("You do not have permission to remove members.")
        
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response({
                "success": False,
                "error": "user_id is required"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        member = CommunityMember.objects.filter(
            community=community,
            user_id=user_id
        ).first()
        
        if not member:
            return Response({
                "success": False,
                "error": "Member not found"
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Can't remove creator
        if member.user == community.created_by:
            return Response({
                "success": False,
                "error": "Cannot remove the community creator"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        member.delete()
        
        return Response({
            "success": True,
            "message": "Member removed successfully",
            "data": None
        })
    
    def _can_manage_community(self, user, community):
        """Check if user can manage the community"""
        if community.created_by == user:
            return True
        
        membership = CommunityMember.objects.filter(
            user=user,
            community=community,
            is_approved=True
        ).first()
        
        return membership and membership.role in ['admin', 'moderator']


class CommunityJoinRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for managing join requests"""
    queryset = CommunityJoinRequest.objects.all()
    serializer_class = CommunityJoinRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'delete']
    
    def get_queryset(self):
        user = self.request.user
        community_name = self.request.query_params.get('community')
        
        # Admins/moderators see all pending requests for their communities
        if community_name:
            try:
                community = Community.objects.get(name=community_name)
                membership = CommunityMember.objects.filter(
                    user=user,
                    community=community,
                    is_approved=True
                ).first()
                
                if membership and membership.role in ['admin', 'moderator']:
                    return CommunityJoinRequest.objects.filter(
                        community=community
                    ).order_by('-created_at')
            except Community.DoesNotExist:
                pass
        
        # Users see their own requests
        return CommunityJoinRequest.objects.filter(user=user).order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a join request"""
        join_request = self.get_object()
        community = join_request.community
        
        # Check permissions
        membership = CommunityMember.objects.filter(
            user=request.user,
            community=community,
            is_approved=True
        ).first()
        
        if not (membership and membership.role in ['admin', 'moderator']):
            raise PermissionDenied("You do not have permission to approve requests.")
        
        # Create membership
        CommunityMember.objects.create(
            user=join_request.user,
            community=community,
            is_approved=True
        )
        
        # Update request
        join_request.status = 'approved'
        join_request.reviewed_by = request.user
        join_request.reviewed_at = timezone.now()
        join_request.save()
        
        # Notify user
        Notification.objects.create(
            recipient=join_request.user,
            sender=request.user,
            notification_type='community_join_approved',
            community=community,
            message=f"approved your request to join {community.title}"
        )
        
        return Response({
            "success": True,
            "message": "Join request approved successfully",
            "data": CommunityJoinRequestSerializer(join_request).data
        })
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a join request"""
        join_request = self.get_object()
        community = join_request.community
        
        # Check permissions
        membership = CommunityMember.objects.filter(
            user=request.user,
            community=community,
            is_approved=True
        ).first()
        
        if not (membership and membership.role in ['admin', 'moderator']):
            raise PermissionDenied("You do not have permission to reject requests.")
        
        join_request.status = 'rejected'
        join_request.reviewed_by = request.user
        join_request.reviewed_at = timezone.now()
        join_request.save()
        
        return Response({
            "success": True,
            "message": "Join request rejected",
            "data": CommunityJoinRequestSerializer(join_request).data
        })