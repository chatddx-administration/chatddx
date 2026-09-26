// The Batch form ticks the variations of the configuration put in, on every
// slice, forgetting what was ticked before, as `use` forgets what was set.
(function () {
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
                    // so that the form's Alpine data hears of it
                    box.dispatchEvent(new Event("change", { bubbles: true }));
                }
            }
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        const select = document.querySelector("select[data-variations]");

        if (select) {
            // select2 tells jQuery of a choice, not the DOM
            django.jQuery(select).on("change", function () {
                tick(select);
            });
        }
    });
})();
