// A case's page: a name offered in place of the one typed, checked again as
// if typed.
function portalCaseName(name) {
    const field = document.getElementById("id_name");

    field.value = name;
    field.dispatchEvent(new Event("input", { bubbles: true }));
}
