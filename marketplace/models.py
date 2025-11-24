# models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify

User = get_user_model()

class Category(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if self.slug is None:
            self.slug = slugify(self.name)
        return super(Category, self).save(*args, **kwargs)

    
class SubCategory(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='subcategories')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (self.category.name + ' - ' + self.name)
    class Meta:
        verbose_name_plural = 'Sub Categories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if self.slug is None:
            self.slug = slugify(self.name)
        return super(SubCategory, self).save(*args, **kwargs)

class Product(models.Model):
    CONDITION_CHOICES = (
        ('new', 'New'),
        ('old', 'Old'),
    )
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('sold', 'Sold'),
        ('unpublished', 'Unpublished'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    image = models.ImageField(upload_to='products')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES, default='new')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    sub_category = models.ForeignKey(SubCategory, on_delete=models.CASCADE, related_name='products')
    color = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['-created_at']
