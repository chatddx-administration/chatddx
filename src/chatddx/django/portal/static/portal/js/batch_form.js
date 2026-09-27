(function() {
    "use strict";

    function tick(select) {
        const own = JSON.parse(select.dataset.variations || "{}")[select.value] || {};

        for (const [slice, name] of Object.entries(own)) {
            const boxes = document.querySelectorAll(
                `input[type="checkbox"][name="${slice}"]`
            );

            for (const box of boxes) {
                const ticked = box.value === name;

                if (box.checked !== ticked) {
                    box.checked = ticked;
                    box.dispatchEvent(new Event("change", { bubbles: true }));
                }
            }
        }
    }

    document.addEventListener("DOMContentLoaded", function() {
        const select = document.querySelector("select[data-variations]");

        if (select) {
            django.jQuery(select).on("change", function() {
                tick(select);
            });
        }
    });
})();
