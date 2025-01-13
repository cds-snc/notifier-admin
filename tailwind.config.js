const plugin = require("tailwindcss/plugin");

module.exports = {
  content: ["./app/**/*.{html,css,js}"],
  safelist: [
    "line-under",
    "flip",
    "phone",
    "bottom-2",
    "bg-red",
    "list-entry-remove",
    "shim",
    "content-fixed",
    "text-gray-grey1",
    "border-gray-grey2",
    "pl-doubleGutter",
    "px-doubleGutter",
    "pt-gutterHalf",
    "mb-12",
    "clear-both",
    "w-auto",
    "text-right",
    "template-list-selected-counter",
    "w-2/3",
    "mb-8",
    "focus:outline-none",
    "w-3/6",
    "pr-gutter",
    "mt-0",
    "max-w-xl",
    "bg-emptyBird",
    "bg-emptyBirdHole",
    "bg-emptyFlower",
    "bg-emptyTruck",
    "bg-emptyBirdCurious",
    "sm:bg-emptyBird",
    "sm:bg-emptyBirdHole",
    "sm:bg-emptyFlower",
    "sm:bg-emptyTruck",
    "sm:bg-emptyBirdCurious",
  ],
  theme: {
    container: {
      center: true,
    },
    boxShadow: {
      outline: "0 0 0 3px rgba(255, 191, 71, 1)" /* yellow */,
      outline2: "0 0 0 2px rgb(38, 55, 74, 1)", // blue-default
      outline4: "0 0 0 4px rgba(255, 191, 71, 1)",
      inset1: "inset -1px 0 0 0 rgb(191, 193, 195)", // theme gray.grey2
      inset3: "inset -3px 0 0 0 rgba(191, 193, 195, 0.2)",
      outset1: "1px 0 0 0 rgb(191, 193, 195)",
      outset2: "0 2px 0 0 rgba(191, 193, 195, 0.2)",
      outset2neg: "0 -2px 0 0 rgba(191, 193, 195, 0.2)",
      outset3: "3px 0 0 0 rgba(191, 193, 195, 0.2)",
      yellow3:
        "-3px 0 0 0 rgba(255, 191, 71, 1), 3px 0 0 0 rgba(255, 191, 71, 1)",
      focusLine2: "0 2px 0 3px #1A3152",
      insetLine2: "inset 0 -2px 0 0 rgb(38, 55, 74, 1)",
      button2: "0 2px 0 rgb(38, 55, 74, 1)",
      none: "none",
    },
    fontSize: {
      xs: "0.875rem",
      small: "1.0625rem",
      smaller: "1.25rem",
      base: "1.25rem",
      title: "1.5rem",
      titlelarge: "1.75rem",
      lg: "2.25rem",
      xxl: "3.25rem",
    },
    screens: {
      xs: "320px",
      smaller: "375px",
      sm: "640px",
      md: "768px",
      lg: "1024px",
    },
    spacing: {
      0: "0rem",
      1: "0.1875rem",
      2: "0.3125rem",
      3: "0.5rem",
      4: "0.625rem",
      5: "0.75rem",
      6: "0.9375rem",
      8: "1.25rem",
      10: "1.5625rem",
      12: "1.875rem",
      16: "2.5rem",
      20: "3.125rem",
      24: "3.75rem",
      56: "8.75rem",
      gutter: "1.875rem",
      gutterHalf: "0.9375rem",
      gutterAndAHalf: "2.8125rem",
      doubleGutter: "3.75rem",
    },
    colors: {
      transparent: "transparent",
      current: "currentColor",
      red: {
        DEFAULT: "#b10e1e",
        hover: "#990c1a",
        border: "#6a0812",
        mellow: "#df3034",
        300: "#D74D42",
      },
      white: "#FFF",
      blue: {
        lighter: "#B2E3FF",
        DEFAULT: "#213045",
        border: "#1A3152",
        selected: "#75b9e0",
        lightblue25: "#d5e8f3",
        lightblue: "#0154B0",
        slightlight: "#284162",
        /* trying to slowly implement a more consistent scale below */
        200: "#D7E5F5",
        300: "#71A7F3",
        500: "#004AB2",
        600: "#6584A6",
        700: "#425A76",
        800: "#31455C",
        900: "#26374A",
      },
      gray: {
        DEFAULT: "#eee",
        button: "#dee0e2" /* grey3 */,
        selected: "#e1e4e7",
        hover: "#d0d3d6",
        border: "#b5babe",
        grey1: "#595959",
        grey2: "#bfc1c3",
        grey4: "#f8f8f8",
        lightgrey: "#C0C1C3",
        visitedlight: "#929AA4",
        visiteddark: "#C8CDD1",
        /* trying to slowly implement a more consistent scale below */
        100: "#F0F2F5",
        200: "#CFD5DD",
        300: "#AFB9C3" /* 3:1 contrast on white */,
        400: "#909CA8",
        500: "#737F8C",
        600: "#5E6975",
        700: "#49535D" /* 7:1 contrast on white */,
        800: "#343C45",
        900: "#21262C",
      },
      yellow: {
        DEFAULT: "#ffbf47",
        light: "#FFE7BB",
      },
      green: {
        DEFAULT: "#00672F",
        darker: "#00703C",
        hover: "#00692f",
        border: "#003618",
        green: "#006435",
        300: "#29A35A",
      },
      black: "#000",
      lime: {
        DEFAULT: "#D3E766",
        100: "#D3E766",
        700: "#545E00",
      },
    },
    extend: {
      animation: {
        ellipsis: "ellipsis steps(4,end) 1.5s infinite",
      },
      backgroundImage: {
        tick: "url('/static/images/tick.svg')",
        crossGrey: "url('/static/images/cross-grey.svg')",
        folder: "url('/static/images/folder-black.svg')",
        folderBlack: "url('/static/images/folder-black-bold.svg')",
        folderBlackPng: "url('/static/images/folder-black-bold.png')",
        folderBlue: "url('/static/images/folder-blue-bold.svg')",
        folderBluePng: "url('/static/images/folder-blue-bold.png')",
        folderBlueHover: "url('/static/images/folder-blue-bold-hover.svg')",
        folderBlueHoverPng: "url('/static/images/folder-blue-bold-hover.png')",
        emptyBird: "url('/static/images/empty-bird.svg')",
        emptyBirdHole: "url('/static/images/empty-bird-hole.svg')",
        emptyFlower: "url('/static/images/empty-flower.svg')",
        emptyTruck: "url('/static/images/empty-truck.svg')",
        emptyBirdCurious: "url('/static/images/empty-bird-curious.svg')",
      },
      backgroundSize: {
        19: "19px",
      },
      borderWidth: {
        1: "1px",
        10: "10px",
      },
      fontFamily: {
        sans: ["lato"],
        body: ["Noto Sans", "Arial", "sans-serif"],
        monospace: ["monospace"],
      },
      inset: {
        2: "2px",
        5: "5px",
        7: "7px",
        full: "100%",
      },
      keyframes: {
        ellipsis: {
          "100%": { width: "1.25em" },
        },
      },
      lineHeight: {
        "extra-tight": "0.9",
      },
      outline: {
        yellow: "3px solid #ffbf47",
        white: "1px solid rgba(255, 255, 255, 0.1)",
        black: "1px solid black",
      },
      transitionDuration: {
        600: "600ms",
      },
      transitionProperty: {
        background: "background",
      },
      width: {
        "5/8": "62.5%",
      },
      maxWidth: {
        "80ch": "80ch",
        "2/3": "66.666667%",
        email: "600px",
      },
      minWidth: {
        target: "45px",
      },
      minHeight: {
        12: "1.875rem",
        target: "45px",
      },
      minWidth: {
        target: "45px",
      },
      flex: {
        2: "2 2 0%",
      },
      zIndex: {
        100: 100,
      },
    },
  },
  plugins: [
    plugin(function ({ addVariant, e }) {
      addVariant("link", ({ modifySelectors, separator }) => {
        modifySelectors(({ className }) => {
          return `.${e(`link${separator}${className}`)}:link`;
        });
      });
    }),
    plugin(function ({ addUtilities, theme }) {
      const individualBorderColors = {
        ".border-b-gray-button": {
          borderBottomColor: theme("colors").gray.button,
        },
        ".border-l-gray-button": {
          borderLeftColor: theme("colors").gray.button,
        },
        ".border-b-gray-grey2": {
          borderBottomColor: theme("colors").gray.grey2,
        },
      };

      addUtilities(individualBorderColors);
    }),
  ],
  variants: {
    backgroundColor: ["responsive", "hover", "focus"],
    borderWidth: ["responsive", "focus"],
    textColor: ["visited", "link", "hover", "focus"],
  },
};
