# serializers.py
from rest_framework import serializers
from .models import Category, SubCategory, UserInterest


class SubCategorySerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(write_only=True)

    class Meta:
        model = SubCategory
        fields = ['id', 'category_name', 'name']

    def create(self, validated_data):
        category_name = validated_data.pop('category_name')
        category = Category.objects.get(name=category_name)
        return SubCategory.objects.create(category=category, **validated_data)


class CategorySerializer(serializers.ModelSerializer):
    subcategories = SubCategorySerializer(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'subcategories']


class UserInterestSerializer(serializers.ModelSerializer):
    subcategories = serializers.PrimaryKeyRelatedField(
        many=True, queryset=SubCategory.objects.all()
    )

    class Meta:
        model = UserInterest
        fields = ['id', 'user', 'subcategories', 'updated_at']
        read_only_fields = ['user', 'updated_at']

    def create(self, validated_data):
        subcategories = validated_data.pop('subcategories', [])
        user = self.context['request'].user
        instance, _ = UserInterest.objects.get_or_create(user=user)
        instance.subcategories.set(subcategories)
        instance.save()
        return instance

    def to_representation(self, instance):
        data = {}
        subcategories = instance.subcategories.select_related('category').all()
        for sub in subcategories:
            category_name = sub.category.name
            if category_name not in data:
                data[category_name] = []
            data[category_name].append({'id': sub.id, 'name': sub.name})
        return data
