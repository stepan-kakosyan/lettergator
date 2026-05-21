// Flatpickr loader for LetterGator using CDN
// This script loads flatpickr from CDN and applies it to the delivery date/time fields on both email and physical letter forms.

document.addEventListener('DOMContentLoaded', function () {
    // Dynamically load flatpickr CSS from CDN
    var flatpickrCss = document.createElement('link');
    flatpickrCss.rel = 'stylesheet';
    flatpickrCss.href = 'https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css';
    document.head.appendChild(flatpickrCss);

    // Dynamically load flatpickr JS from CDN
    var flatpickrScript = document.createElement('script');
    flatpickrScript.src = 'https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.js';
    flatpickrScript.onload = function () {
        // Email letter form
        var emailDelivery = document.getElementById('id_delivery_at');
        if (emailDelivery) {
            flatpickr(emailDelivery, {
                enableTime: true,
                dateFormat: 'Y-m-d H:i',
                time_24hr: true,
                allowInput: true,
                defaultHour: 12,
                minuteIncrement: 1,
            });
        }
        // Physical letter form (if it exists)
        var physicalDelivery = document.getElementById('id_requested_delivery_date');
        if (physicalDelivery) {
            flatpickr(physicalDelivery, {
                enableTime: false,
                dateFormat: 'Y-m-d',
                allowInput: true,
            });
        }
    };
    document.body.appendChild(flatpickrScript);
});
