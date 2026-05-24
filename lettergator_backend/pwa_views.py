from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
from django.shortcuts import render


@require_GET
def manifest(request):
    return JsonResponse({
        "name": "LetterGator",
        "short_name": "LetterGator",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#014421",
        "description": "Send letters, physical or digital, worldwide.",
        "icons": [
            {
                "src": "/static/img/logo192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/static/img/logo512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }, content_type="application/manifest+json")


@require_GET
@never_cache
def service_worker(request):
    response = render(request, "/static/js/service-worker.js", content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    return response


@require_GET
def offline(request):
    return render(request, "accounts/offline.html")
