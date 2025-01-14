/*
 * This module enhances the template content text area with a switch to enable right-to-left text direction.
 */
(function () {
  const checkbox = document.getElementById("text_direction_rtl");
  const content = document.getElementById("template_content");

  // update the dir attribute when checkbox is clicked
  if (checkbox) {
    checkbox.addEventListener("change", function () {
      content.dir = this.checked ? "rtl" : "ltr";
      content.closest(".textbox-highlight-wrapper").dir = content.dir;
    });

    // on page load, if the checkbox is checked, set the dir attribute
    if (checkbox.checked) {
      content.dir = "rtl";
    }
  }
})();
