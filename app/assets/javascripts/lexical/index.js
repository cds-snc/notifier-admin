import React, { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { RichTextEditor } from "./RichTextEditor";
import "./styles.css";

// read properties from the script tag
const scriptTag = document.currentScript;
const data = scriptTag.dataset;

if (data.id === undefined || data.id === "") {
  console.error(
    "rich_text_component (lexical): A data-id property is required on the script tag to tell the component which element to render into.",
  );
}

const rootElement = document.getElementById(`root_${data.id}`);

createRoot(rootElement).render(
  <StrictMode>
    <RichTextEditor
      path="path.to.content"
      content={data.content}
      ariaLabel="AriaLabel"
      lang="en"
      id={data.id}
    />
  </StrictMode>,
);
