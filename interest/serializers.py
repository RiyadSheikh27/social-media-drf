# serializers.py
from rest_framework import serializers
from .models import *

""" Serializers for Interest """
class SubCategorySerializer(serializers.ModelSerializer):
    """ Serializer for SubCategory """
    category_name = serializers.CharField(write_only=True)
    class Meta:
        model = SubCategory
        fields = ['id', 'category_name', 'name']

    def create(self, validated_data):
        category_name = validated_data.pop('category_name')
        category = Category.objects.get(name=category_name)
        return SubCategory.objects.create(category=category, **validated_data)


class CategorySerializer(serializers.ModelSerializer):
    """ Serializer for Category """
    subcategories = SubCategorySerializer(many=True, read_only=True)
    class Meta:
        model = Category
        fields = ['id', 'name', 'subcategories']

""" End of Serializers for Interest """