from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from .models import *
from .serializers import *

""" Custom Responses """
def success_response(message, data=None, code=status.HTTP_200_OK):
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
""" End of Custom Responses """

""" Viewset for Interest """
class CategoryViewSet(viewsets.ModelViewSet):
    """ Viewset for Category """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]

    # List all
    def list(self, request, *args, **kwargs):
        categories = self.get_queryset()
        serializer = self.get_serializer(categories, many=True)
        return success_response("All categories fetched successfully", serializer.data)

    # Retrieve single
    def retrieve(self, request, *args, **kwargs):
        category = self.get_object()
        serializer = self.get_serializer(category)
        return success_response("Category fetched successfully", serializer.data)

    # Create
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return success_response("Category created successfully", serializer.data, status.HTTP_201_CREATED)
        return error_response(serializer.errors)

    # Update (PUT)
    def update(self, request, *args, **kwargs):
        category = self.get_object()
        serializer = self.get_serializer(category, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return success_response("Category updated successfully", serializer.data)
        return error_response(serializer.errors)

    # Partial Update (PATCH)
    def partial_update(self, request, *args, **kwargs):
        category = self.get_object()
        serializer = self.get_serializer(category, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return success_response("Category partially updated", serializer.data)
        return error_response(serializer.errors)

    # Delete
    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        category.delete()
        return success_response("Category deleted successfully", None, status.HTTP_204_NO_CONTENT)

class SubCategoryViewSet(viewsets.ModelViewSet):
    """ Viewset for SubCategory """
    queryset = SubCategory.objects.all()
    serializer_class = SubCategorySerializer
    permission_classes = [permissions.AllowAny]

    # List all
    def list(self, request, *args, **kwargs):
        sub_categories = self.get_queryset()
        serializer = self.get_serializer(sub_categories, many=True)
        return success_response("All sub-categories fetched successfully", serializer.data)

    # Retrieve single
    def retrieve(self, request, *args, **kwargs):
        subcat = self.get_object()
        serializer = self.get_serializer(subcat)
        return success_response("Sub-category fetched successfully", serializer.data)

    # Create
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return success_response("Sub-category created successfully", serializer.data, status.HTTP_201_CREATED)
        return error_response(serializer.errors)

    # Update
    def update(self, request, *args, **kwargs):
        subcat = self.get_object()
        serializer = self.get_serializer(subcat, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return success_response("Sub-category updated successfully", serializer.data)
        return error_response(serializer.errors)

    # Partial update
    def partial_update(self, request, *args, **kwargs):
        subcat = self.get_object()
        serializer = self.get_serializer(subcat, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return success_response("Sub-category partially updated", serializer.data)
        return error_response(serializer.errors)

    # Delete
    def destroy(self, request, *args, **kwargs):
        subcat = self.get_object()
        subcat.delete()
        return success_response("Sub-category deleted successfully", None, status.HTTP_204_NO_CONTENT)
    
""" End of Viewset for Interest """