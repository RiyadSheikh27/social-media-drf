from django.contrib import admin
from .models import *

# Register your models here.
admin.site.register(Post)
admin.site.register(Like)
admin.site.register(Comment)
admin.site.register(Share)
admin.site.register(Follow)
admin.site.register(Notification)
admin.site.register(PostView)