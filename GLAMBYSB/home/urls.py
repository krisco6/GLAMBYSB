from django.urls import path
from .views import HomeView, OrderView  # Ensure the correct import
from . import views
urlpatterns = [
    path('', HomeView.as_view(), name='index'),  # Use .as_view() here
    path('new-products/', views.new_products, name='new-products'),
    path('about_us/', views.about_us, name='about_us'),
    path('brands',views.brands,name='brands'),
    path('brand-autocomplete/', views.brand_autocomplete, name='brand-autocomplete'),
    path('weekly/portal/', OrderView.as_view(), name='order_submission'),
    path('contact/', views.contact, name='contact'),

]
