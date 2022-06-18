urlpatterns = [
    
    path('blog/', ('blog.urls')),
    # path('ckeditor/', include('ckeditor_uploader.urls')),

]
# You can use the URLs provided by blog: `post_list`, `post_detail`, `post_tag`, `post_update`, `post_delete`, `post_create`, `search_blog`, `user_post`

# now add the following lines of code

from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

from django.contrib import admin
from django.urls import path

urlpatterns = [
    path('admin/', admin.site.urls),
]
