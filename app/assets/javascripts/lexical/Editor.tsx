import React, { useState } from "react";
import PropTypes from "prop-types";
import { LexicalComposer } from "@lexical/react/LexicalComposer";
import { ListPlugin } from "@lexical/react/LexicalListPlugin";
import { RichTextPlugin } from "@lexical/react/LexicalRichTextPlugin";
import { OnChangePlugin } from "@lexical/react/LexicalOnChangePlugin";
import { HistoryPlugin } from "@lexical/react/LexicalHistoryPlugin";
import { ContentEditable } from "@lexical/react/LexicalContentEditable";
import LexicalErrorBoundary from "@lexical/react/LexicalErrorBoundary";
import { $createParagraphNode, $getRoot } from "lexical";
import { editorConfig } from "./config";
import { Toolbar } from "./Toolbar";
import { LinkPlugin } from "@lexical/react/LexicalLinkPlugin";
import {
  $convertFromMarkdownString,
  $convertToMarkdownString,
} from "@lexical/markdown";
import { MarkdownShortcutPlugin } from "@lexical/react/LexicalMarkdownShortcutPlugin";
import TRANSFORMERS from "./transformers";

import FloatingLinkEditorPlugin from "./plugins/FloatingLinkEditorPlugin";
import ListMaxIndentPlugin from "./plugins/ListMaxIndentPlugin";
import TabIndentationPlugin from "./plugins/TabIndentationPlugin";
import HorizontalRulePlugin from "./plugins/HorizontalRulePlugin";

export const Editor = ({
  content,
  onChange,
  ariaLabel,
  ariaDescribedBy,
  lang,
}: {
  content: string;
  onChange: (value: string) => void;
  ariaLabel?: string;
  ariaDescribedBy?: string;
  lang?: string;
}) => {
  const [floatingAnchorElem, setFloatingAnchorElem] = useState<
    HTMLDivElement | undefined
  >(undefined);

  const editorId = "editor-" + Math.random().toString(36).substr(2, 9);

  const onRef = (_floatingAnchorElem: HTMLDivElement) => {
    if (_floatingAnchorElem !== null) {
      setFloatingAnchorElem(_floatingAnchorElem);
    }
  };

  if (typeof content !== "string") {
    content = "";
  }
  return (
    <div className="rich-text-wrapper">
      <LexicalComposer
        initialConfig={{
          ...editorConfig,
          editorState: () => {
            if (!content) {
              const root = $getRoot();
              const paragraphNode = $createParagraphNode();
              root.append(paragraphNode);
              return;
            }
            $convertFromMarkdownString(content, TRANSFORMERS);
          },
        }}
      >
        <Toolbar editorId={editorId} />
        <RichTextPlugin
          contentEditable={
            <div
              className="editor relative"
              ref={onRef}
              {...(lang && { lang: lang })}
            >
              <ContentEditable
                className="editor-input focus:outline-blue-focus"
                id={editorId}
                ariaLabel="Content editor: edit or create your content here. To apply formatting,
                select the desired text and press shift+tab to return to the toolbar and select
                an option.  You can also use markdown formatting directly in the editor."
                ariaDescribedBy={ariaDescribedBy && ariaDescribedBy}
              />
            </div>
          }
          placeholder={null}
          ErrorBoundary={LexicalErrorBoundary}
        />
        <HistoryPlugin />
        <OnChangePlugin
          onChange={(editorState) => {
            editorState.read(() => {
              // Read the contents of the EditorState here.
              const markdown = $convertToMarkdownString(TRANSFORMERS);

              // Add two spaces to previous line for linebreaks (this is not handled properly by $convertToMarkdownString)
              const lines = markdown.split("\n");
              lines.forEach((currentLine, i) => {
                if (i > 0) {
                  const previousLine = lines[i - 1];
                  if (previousLine !== "" && currentLine !== "") {
                    lines[i - 1] = previousLine.trim() + "  ";
                  }
                }
              });
              onChange(lines.join("\n"));
            });
          }}
        />
        <LinkPlugin />
        <FloatingLinkEditorPlugin anchorElem={floatingAnchorElem} />
        <ListPlugin />
        <ListMaxIndentPlugin maxDepth={5} />
        {/* <TabIndentationPlugin /> */}
        <MarkdownShortcutPlugin transformers={TRANSFORMERS} />
        <HorizontalRulePlugin />
      </LexicalComposer>
    </div>
  );
};

Editor.propTypes = {
  id: PropTypes.string,
  content: PropTypes.string,
  onChange: PropTypes.func,
};
