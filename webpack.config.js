const path = require("path");
const webpack = require("webpack");
const MiniCssExtractPlugin = require("mini-css-extract-plugin");

module.exports = {
  target: "web",
  // mode: "development", //development
  mode: "production",
  entry: {
    main: ["./app/assets/javascripts/index.js", "./app/assets/stylesheets/tailwind/style.css"],
    branding_request: ["./app/assets/javascripts/branding_request.js"],
    formValidateRequired: ["./app/assets/javascripts/formValidateRequired.js"],
    sessionRedirect: ["./app/assets/javascripts/sessionRedirect.js"],
    touDialog: ["./app/assets/javascripts/touDialog.js"],
    templateFilters: ["./app/assets/javascripts/templateFilters.js"],
    scheduler: {
      import: './app/assets/javascripts/scheduler/scheduler.js',
      library: {
        name: 'Scheduler',
        type: 'window',
      },
    },
    lexical: {
      import: './app/assets/javascripts/lexical/index.js',
    }
  },
  watch: false,
  output: {
    filename: "javascripts/[name].min.js",
    path: path.resolve(__dirname, "app/assets")
  },

  plugins: [
    new webpack.ProgressPlugin(),
    new MiniCssExtractPlugin({
      filename: 'stylesheets/index.css',
      path: path.resolve(__dirname, "app/assets/stylesheets")
    }),
  ],

  module: {
    rules: [
      {
        test: /\.css$/i,
        include: [
          path.resolve(__dirname, "app/assets/javascripts")
        ],
        use: ["style-loader", "css-loader"]
      },
      {
        test: /\.css$/i,
        include: [
          path.resolve(__dirname, "app/assets/stylesheets/tailwind")
        ],
        use: [
          MiniCssExtractPlugin.loader,
          "css-loader",
          "postcss-loader"
        ]
      },
      { 
        test: /\.(png|svg|jpg|gif|ico)$/, 
        use: [
          {
            loader: 'file-loader', 
            options: {
              name: '[name].[ext]',
              outputPath: 'images/lexical',
              esModule: false,
            },
          },
        ],
      },
      {
        test: /.(js|jsx)$/,
        include: [path.resolve(__dirname, "app/assets/javascripts")],
        loader: "babel-loader",
        options: {
          plugins: ["syntax-dynamic-import"],

          presets: [
            [
              "@babel/preset-env",
              {
                modules: false
              }
            ]
          ]
        }
      },
      {
        test: /.(ts|tsx)$/,
        use: 'ts-loader',
        exclude: /node_modules/,
      },
    ]
  },
  resolve: {
    extensions: ['.ts', '.js', '.json', '.tsx']
  }
};
