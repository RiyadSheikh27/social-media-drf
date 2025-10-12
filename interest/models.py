from django.db import models
from accounts.models import *

# Create your models here.
class InterestCategory(models.Model):
    category = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.category)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.category
    
    class Meta:
        verbose_name_plural = "Interest Categories"

class InterestSubCategory(models.Model):
    category = models.ForeignKey(InterestCategory, on_delete=models.CASCADE)
    subcategory = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.category.category} - {self.subcategory}"
    

class Interest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    interest = models.ForeignKey(InterestSubCategory, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.user.username} - {self.interest.subcategory}"