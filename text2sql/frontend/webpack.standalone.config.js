const path = require("path");

module.exports = {
  entry: "./src/standalone.tsx",
  output: {
    clean: false,
    filename: "bi-ai-text2sql.standalone.js",
    path: path.resolve(__dirname, "dist"),
    publicPath: "/api/v1/extensions/bi-ai.text2sql/",
  },
  resolve: {
    extensions: [".ts", ".tsx", ".js", ".jsx"],
  },
  module: {
    rules: [
      {
        test: /\.tsx?$/,
        use: "ts-loader",
        exclude: /node_modules/,
      },
    ],
  },
};
