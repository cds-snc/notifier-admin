import MainMenu from "../../../Notify/Admin/Pages/MainMenu";

/* test that the main menu works on mobile. will need to set viewport to 414x896 */
describe("Mobile menu", () => {
  beforeEach(() => {
    cy.viewport(414, 896);
    cy.visit("/");
  });

  const a11yCheck = () => {
    cy.injectAxe();
    cy.checkA11y();
    cy.get("header").htmlvalidate();
  };

  it("Is accessible and has valid HTML", () => {
    // check menu when its closed
    a11yCheck();

    // check menu when its open
    MainMenu.OpenMenu();
    a11yCheck();
  });

  it("Open and close the menu using ESC and clicking", () => {
    MainMenu.OpenMenu();

    MainMenu.Components.Menu().should("be.visible");
    MainMenu.Components.MenuItems().then((menuItems) => {
      // first menu item should be focused
      cy.get(menuItems[0]).should("have.focus");
    });

    // close menu on esc
    MainMenu.CloseMenuEsc();
    MainMenu.Components.Menu().should("not.be.visible");

    // open menu
    MainMenu.OpenMenu();

    // close menu when clicking outside
    MainMenu.CloseMenuClick();
    MainMenu.Components.Menu().should("not.be.visible");
  });

  it("Navigate the menu forward using right arrow, down arrow", () => {
    cy.then(Cypress.session.clearCurrentSessionData);
    MainMenu.OpenMenu();
    MainMenu.Components.Menu().should("be.visible"); // menu should be visible

    // press arrow right to focus the next menu item
    MainMenu.ArrowRight();
    MainMenu.Components.MenuItems().then((menuItems) => {
      // second menu item should be focused
      cy.get(menuItems[1]).should("have.focus");
    });

    // press arrow down to focus the next menu item
    MainMenu.ArrowDown();
    MainMenu.Components.MenuItems().then((menuItems) => {
      // second menu item should be focused
      cy.get(menuItems[2]).should("have.focus");
    });
  });

  it("Navigate the menu backward using left arrow, up arrow", () => {
    cy.then(Cypress.session.clearCurrentSessionData);
    MainMenu.OpenMenu();
    MainMenu.Components.Menu().should("be.visible"); // menu should be visible

    // press arrow left to focus the previous menu item
    MainMenu.ArrowLeft();
    MainMenu.Components.MenuItems().then((menuItems) => {
      // second menu item should be focused
      cy.get(menuItems[menuItems.length - 1]).should("have.focus");
    });

    // press arrow up to focus the previous menu item
    MainMenu.ArrowUp();
    MainMenu.Components.MenuItems().then((menuItems) => {
      // second menu item should be focused
      cy.get(menuItems[menuItems.length - 2]).should("have.focus");
    });
  });

  it("Start at the first menu item each time", () => {
    cy.then(Cypress.session.clearCurrentSessionData);
    MainMenu.OpenMenu();
    MainMenu.Components.Menu().should("be.visible"); // menu should be visible

    MainMenu.Components.MenuItems().then((menuItems) => {
      // first menu item should be focused
      cy.get(menuItems[0]).should("have.focus");
    });

    // press arrow right to focus the next menu item
    MainMenu.ArrowRight();
    MainMenu.Components.MenuItems().then((menuItems) => {
      // second menu item should be focused
      cy.get(menuItems[1]).should("have.focus");
    });

    // close menu
    MainMenu.CloseMenuEsc();
    MainMenu.Components.Menu().should("not.be.visible");

    // open menu
    MainMenu.OpenMenu();
    MainMenu.Components.Menu().should("be.visible"); // menu should be visible
    MainMenu.Components.MenuItems().then((menuItems) => {
      // first menu item should be focused
      cy.get(menuItems[0]).should("have.focus");
    });

    // press arrow right to focus the next menu item
    MainMenu.ArrowRight();
    MainMenu.Components.MenuItems().then((menuItems) => {
      // second menu item should be focused
      cy.get(menuItems[1]).should("have.focus");
    });
  });

  it("Re-focus on the menu button when the menu closes (signed out)", () => {
    cy.then(Cypress.session.clearCurrentSessionData);
    MainMenu.OpenMenu();
    MainMenu.Components.Menu().should("be.visible"); // menu should be visible

    // press esc to close the menu
    MainMenu.CloseMenuEsc();
    MainMenu.Components.Menu().should("not.be.visible");

    // menu button should be focused
    MainMenu.Components.MenuButton().should("have.focus");
  });

  it("Re-focus on the menu button when the menu closes (signed in)", () => {
    cy.login();

    cy.visit("/");
    MainMenu.OpenMenu();
    MainMenu.Components.Menu().should("be.visible"); // menu should be visible

    // press esc to close the menu
    MainMenu.CloseMenuEsc();
    MainMenu.Components.Menu().should("not.be.visible");

    // menu button should be focused
    MainMenu.Components.MenuButton().should("have.focus");
  });
});
