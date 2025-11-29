from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register(Community)
admin.site.register(CommunityMember)
admin.site.register(CommunityRule)
admin.site.register(CommunityInvitation)
admin.site.register(CommunityJoinRequest)