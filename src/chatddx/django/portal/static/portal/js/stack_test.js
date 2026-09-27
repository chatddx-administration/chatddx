async function portalTest(form) {
    const section = form.closest("section");
    const button = form.querySelector("button");
    const lists = {
        server: section.querySelector("#checks-server"),
        llm: section.querySelector("#checks-llm"),
    };

    button.disabled = true;
    section.querySelector(".portal-test-broken")?.remove();

    try {
        const response = await fetch(form.action, {
            method: "POST",
            body: new FormData(form),
            headers: { Accept: "application/x-ndjson" },
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
        let rest = "";

        for (; ;) {
            const { value, done } = await reader.read();

            if (done) {
                break;
            }

            const lines = (rest + value).split("\n");
            rest = lines.pop();

            for (const line of lines) {
                if (line.trim()) {
                    portalTestEvent(lists, JSON.parse(line));
                }
            }
        }
    } catch (error) {
        const broken = document.createElement("p");
        broken.className = "portal-test-broken portal-refused text-sm";
        broken.textContent = `${section.dataset.brokeOff} ${error.message}`;
        section.querySelector(".portal-checks").before(broken);
    } finally {
        button.disabled = false;
    }
}

function portalTestEvent(lists, event) {
    if (event.html !== undefined) {
        const holder = document.createElement("template");
        holder.innerHTML = event.html.trim();

        const check = holder.content.firstElementChild;
        const standing = document.getElementById(check.id);

        if (standing) {
            standing.replaceWith(check);
        } else {
            lists[event.group].append(check);
        }

        return;
    }

    const into = document.querySelector(
        `#check-${event.check} [data-stream="${event.stream}"]`,
    );

    into?.append(event.text);
}
