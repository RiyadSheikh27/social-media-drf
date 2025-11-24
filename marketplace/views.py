from django.shortcuts import render
from .models import *
from .serializers import *
from accounts.permissions import *
from rest_framework import viewsets
from rest_framework import status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404

user = get_user_model()

# Create your views here.
def success_response(message, data=None, code =status.HTTP_200_OK):
    return Response({
        'success': True,
        'message': message,
        'data': data
    }, status=code)

def error_response(message, code=status.HTTP_400_BAD_REQUEST):
    return Response({
        'success': False,
        'message': message
    }, status=code)

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return success_response("Category list retrieved successfully.", serializer.data)

    def retrieve(self, request, pk=None, *args, **kwargs):
        category = get_object_or_404(Category, pk=pk)
        serializer = self.get_serializer(category)
        return success_response("Category retrieved successfully.", serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return success_response("Category created successfully.", serializer.data, status.HTTP_201_CREATED)

        return error_response("Category creation failed.", serializer.errors)

    def update(self, request, pk=None, *args, **kwargs):
        category = get_object_or_404(Category, pk=pk)
        serializer = self.get_serializer(category, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return success_response("Category updated successfully.", serializer.data)

        return error_response("Category update failed.", serializer.errors)

    def destroy(self, request, pk=None, *args, **kwargs):
        category = get_object_or_404(Category, pk=pk)
        category.delete()
        return success_response("Category deleted successfully.", None, status.HTTP_204_NO_CONTENT)