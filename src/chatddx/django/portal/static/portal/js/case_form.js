function portalCaseName(name) {
    const field = document.getElementById("id_name");

    field.value = name;
    field.dispatchEvent(new Event("input", { bubbles: true }));
}
