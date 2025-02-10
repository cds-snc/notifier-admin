import Notice from "../../../Notify/Admin/Components/Notice";

let PageURL = "/_storybook?component=notice";

describe("Notice component", () => {
  it("Should pass a11y checks", () => {
    cy.a11yScan(PageURL, {
      a11y: true,
      htmlValidate: true,
      deadLinks: false,
      mimeTypes: false,
    });
  });

  it("Should use the correct icon depending on type", () => {
    cy.visit(PageURL);

    // info notice component should be info
    Notice.Components.Icon("info").should("have.class", "fa-circle-info");

    // success notice component should be success
    Notice.Components.Icon("success").should("have.class", "fa-circle-check");

    // warning notice component should be warning
    Notice.Components.Icon("warning").should(
      "have.class",
      "fa-circle-exclamation",
    );

    // error notice component should be error
    Notice.Components.Icon("error").should(
      "have.class",
      "fa-triangle-exclamation",
    );
  });

  it("Should the correct alternative text for the icon", () => {
    cy.visit(PageURL);

    // info notice component should have alt text "Information"
    Notice.Components.IconText("info").should("have.text", "Information: ");

    // success notice component should have alt text "Success"
    Notice.Components.IconText("success").should("have.text", "Success: ");

    // warning notice component should have alt text "Warning"
    Notice.Components.IconText("warning").should("have.text", "Warning: ");

    // error notice component should have alt text "Error"
    Notice.Components.IconText("error").should("have.text", "Error: ");
  });
});
