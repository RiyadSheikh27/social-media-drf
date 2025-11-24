from .models import *
from rest_framework import serializers
from django.contrib.auth import get_user_model

user = get_user_model()

class SubCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = SubCategory
        fields = ['id', 'name', 'category', 'created_at']

        read_only_fields = ['id','created_at']


class CategorySerializer(serializers.ModelSerializer):
    subcategories = SubCategorySerializer(many=True, read_only=True)
    subcategory_count = serializers.IntegerField(read_only=True)
    class Meta:
        model = Category
        fields = ['id', 'name', 'subcategories', 'subcategory_count', 'created_at']

        read_only_fields = ['id', 'created_at']

    def get_subcategory_count(self, obj):
        return obj.subcategories.count()

class ProductSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.username', read_only=True)
    category_name = serializers.CharField(source='sub_category.category.name', read_only=True)
    subcategory_name = serializers.CharField(source='sub_category.name', read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'image', 'price', 'condition', 'status', 'user_name', 'category_name', 'subcategory_name', 'color', 'description', 'location', 'created_at', 'updated_at']

        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user

        return super().create(validated_data)
    
class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views"""
    user_name = serializers.CharField(source='user.username', read_only=True)
    category_name = serializers.CharField(source='sub_category.category.name', read_only=True)
    sub_category_name = serializers.CharField(source='sub_category.name', read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'user_name', 'name', 'image', 'price', 
            'condition', 'status', 'sub_category_name', 
            'category_name', 'location', 'created_at'
        ]


