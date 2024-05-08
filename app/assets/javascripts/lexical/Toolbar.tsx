import React, {
  useState,
  useCallback,
  useEffect,
  useRef,
  KeyboardEvent,
} from "react";
import { useLexicalComposerContext } from "@lexical/react/LexicalComposerContext";
import { $isHeadingNode, $createHeadingNode } from "@lexical/rich-text";
import { mergeRegister, $getNearestNodeOfType } from "@lexical/utils";

import { $isLinkNode, TOGGLE_LINK_COMMAND } from "@lexical/link";
import { useTranslation } from "react-i18next";

import {
  $isListNode,
  INSERT_ORDERED_LIST_COMMAND,
  INSERT_UNORDERED_LIST_COMMAND,
  REMOVE_LIST_COMMAND,
  ListNode,
} from "@lexical/list";

import {
  FORMAT_TEXT_COMMAND,
  $getSelection,
  $isRangeSelection,
  SELECTION_CHANGE_COMMAND,
  $createParagraphNode,
} from "lexical";

import { INSERT_HORIZONTAL_RULE_COMMAND } from "@lexical/react/LexicalHorizontalRuleNode";

import { $wrapNodes } from "@lexical/selection";
import { sanitizeUrl } from "./utils/url";
import { useEditorFocus } from "./useEditorFocus";
import { getSelectedNode } from "./utils/getSelectedNode";
import { ToolTip } from "./ToolTip";

const blockTypeToBlockName = {
  bullet: "Bulleted List",
  check: "Check List",
  code: "Code Block",
  h1: "Heading 1",
  h2: "Heading 2",
  h3: "Heading 3",
  h4: "Heading 4",
  h5: "Heading 5",
  h6: "Heading 6",
  number: "Numbered List",
  paragraph: "Normal",
  quote: "Quote",
};

const LowPriority = 1;
type HeadingTagType = "h1" | "h2" | "h3" | "h4" | "h5";

interface TooltipsType {
  [key: string]: string;
}

const TOOLTIPS: TooltipsType = {
  "tooltipFormatH1": "Heading level 1",
  "tooltipFormatH2": "Heading level 2",
  "tooltipFormatBold": "Bold (⌘B)",
  "tooltipFormatItalic": "Italic (⌘I)",
  "tooltipFormatBulletList": "Bulleted list",
  "tooltipFormatNumberedList": "Numbered list",
  "tooltipInsertLink": "Insert link",
  "tooltipInsertHR": "Insert horiz. rule",
}

function t(tooltip_name: string): string {
  return TOOLTIPS[tooltip_name];
}

export const Toolbar = ({ editorId }: { editorId: string }) => {
  const [editor] = useLexicalComposerContext();
  const [isBold, setIsBold] = useState(false);
  const [isItalic, setIsItalic] = useState(false);
  const [isLink, setIsLink] = useState(false);
  const [, setSelectedElementKey] = useState("");
  const [blockType, setBlockType] = useState("paragraph");

  const [isEditable] = useState(() => editor.isEditable());

  const insertLink = useCallback(() => {
    if (!isLink) {
      editor.dispatchCommand(TOGGLE_LINK_COMMAND, sanitizeUrl("https://"));
    } else {
      editor.dispatchCommand(TOGGLE_LINK_COMMAND, null);
    }
  }, [editor, isLink]);

  const insertHR = useCallback(() => {
    editor.dispatchCommand(INSERT_HORIZONTAL_RULE_COMMAND, null);
  }, [editor]);

  const [items] = useState([
    { id: 1, txt: "heading1" },
    { id: 2, txt: "heading2" },
    { id: 3, txt: "bold" },
    { id: 4, txt: "italic" },
    { id: 5, txt: "bulletedList" },
    { id: 6, txt: "numberedList" },
    { id: 7, txt: "link" },
  ]);

  const itemsRef = useRef<[HTMLButtonElement] | []>([]);
  const [currentFocusIndex, setCurrentFocusIndex] = useState(0);
  const [toolbarInit, setToolbarInit] = useState(false);

  useEffect(() => {
    const index = `button-${currentFocusIndex}` as unknown as number;
    const el = itemsRef.current[index];
    if (el && toolbarInit) {
      el.focus();
    }
  }, [currentFocusIndex, toolbarInit]);

  const handleNav = useCallback(
    (evt: KeyboardEvent<HTMLInputElement>) => {
      const { key } = evt;

      if (!toolbarInit) {
        setCurrentFocusIndex(0);
        setToolbarInit(true);
      }

      if (key === "ArrowLeft") {
        evt.preventDefault();
        setCurrentFocusIndex((index) => Math.max(0, index - 1));
      } else if (key === "ArrowRight") {
        evt.preventDefault();
        setCurrentFocusIndex((index) => Math.min(items.length - 1, index + 1));
      }
    },
    [items, setCurrentFocusIndex, setToolbarInit, toolbarInit],
  );

  const formatHeading = (level: HeadingTagType) => {
    if (blockType === level) {
      formatParagraph();
    }

    if (blockType !== level) {
      editor.update(() => {
        const selection = $getSelection();
        if ($isRangeSelection(selection)) {
          $wrapNodes(selection, () => $createHeadingNode(level));
        }
      });
    }
  };

  const formatParagraph = () => {
    if (blockType !== "paragraph") {
      editor.update(() => {
        const selection = $getSelection();

        if ($isRangeSelection(selection)) {
          $wrapNodes(selection, () => $createParagraphNode());
        }
      });
    }
  };

  const formatBulletList = (evt: React.MouseEvent<HTMLButtonElement>) => {
    evt.preventDefault();
    if (blockType !== "bullet") {
      editor.dispatchCommand(INSERT_UNORDERED_LIST_COMMAND, undefined);
      return;
    }
    editor.dispatchCommand(REMOVE_LIST_COMMAND, undefined);
  };

  const formatNumberedList = (evt: React.MouseEvent<HTMLButtonElement>) => {
    evt.preventDefault();
    if (blockType !== "number") {
      editor.dispatchCommand(INSERT_ORDERED_LIST_COMMAND, undefined);
      return;
    }
    editor.dispatchCommand(REMOVE_LIST_COMMAND, undefined);
  };

  const updateToolbar = useCallback(() => {
    const selection = $getSelection();

    if ($isRangeSelection(selection)) {
      const anchorNode = selection.anchor.getNode();
      const element =
        anchorNode.getKey() === "root"
          ? anchorNode
          : anchorNode.getTopLevelElementOrThrow();
      const elementKey = element.getKey();
      const elementDOM = editor.getElementByKey(elementKey);
      if (elementDOM !== null) {
        setSelectedElementKey(elementKey);

        const type = $isHeadingNode(element)
          ? element.getTag()
          : element.getType();
        setBlockType(type);
      }

      // Update text format
      setIsBold(selection.hasFormat("bold"));
      setIsItalic(selection.hasFormat("italic"));

      // Get current node and parent
      const node = getSelectedNode(selection);
      const parent = node.getParent();

      // Update links
      if ($isLinkNode(parent) || $isLinkNode(node)) {
        setIsLink(true);
      } else {
        setIsLink(false);
      }

      if (elementDOM !== null) {
        setSelectedElementKey(elementKey);
        if ($isListNode(element)) {
          const parentList = $getNearestNodeOfType<ListNode>(
            anchorNode,
            ListNode,
          );
          const type = parentList
            ? parentList.getListType()
            : element.getListType();
          setBlockType(type);
        } else {
          const type = $isHeadingNode(element)
            ? element.getTag()
            : element.getType();
          if (type in blockTypeToBlockName) {
            setBlockType(type as keyof typeof blockTypeToBlockName);
          }
        }
      }
    }
  }, [editor]);

  useEffect(() => {
    return mergeRegister(
      editor.registerUpdateListener(({ editorState }) => {
        editorState.read(() => {
          updateToolbar();
        });
      }),
      editor.registerCommand(
        SELECTION_CHANGE_COMMAND,
        () => {
          updateToolbar();
          return false;
        },
        LowPriority,
      ),
    );
  }, [editor, updateToolbar]);


  const editorHasFocus = useEditorFocus();

  return (
    <>
      <div
        className="toolbar-container"
        role="toolbar"
        tabIndex={0}
        aria-label="Template toolbar: press the left and right arrow keys to see see 
          the formatting options; press tab to enter the content area"
        aria-controls={editorId}
        onKeyDown={handleNav}
        data-testid="toolbar"
      >
        <ToolTip text={t("tooltipFormatH1")}>
          <button
            type="button"
            tabIndex={currentFocusIndex == 0 ? 0 : -1}
            ref={(el) => {
              const index = "button-0" as unknown as number;
              if (el && itemsRef.current) {
                itemsRef.current[index] = el;
              }
            }}
            onClick={() => {
              formatHeading("h1");
            }}
            className={
              "toolbar-item spaced double " +
              (blockType === "h1" && editorHasFocus ? "active" : "")
            }
            aria-label="Format heading level 1"
            aria-pressed={blockType === "h1"}
            data-testid={`h1-button`}
          >
            <i
              aria-hidden="true"
              className="p-1 fa-solid fa-fas fa-heading"
            ></i>
            <i aria-hidden="true" className="p-1 fa-solid fa-fas fa-1"></i>
          </button>
        </ToolTip>

        <ToolTip text={t("tooltipFormatH2")}>
          <button
            type="button"
            tabIndex={currentFocusIndex == 1 ? 0 : -1}
            ref={(el) => {
              const index = "button-1" as unknown as number;
              if (el && itemsRef.current) {
                itemsRef.current[index] = el;
              }
            }}
            onClick={() => {
              formatHeading("h2");
            }}
            className={
              "peer toolbar-item spaced double " +
              (blockType === "h2" && editorHasFocus ? "active" : "")
            }
            aria-label="Format heading level 2"
            aria-pressed={blockType === "h2"}
            data-testid={`h2-button`}
          >
            <i
              aria-hidden="true"
              className="p-1 fa-solid fa-fas fa-heading"
            ></i>
            <i aria-hidden="true" className="p-1 fa-solid fa-fas fa-2"></i>
          </button>
        </ToolTip>

        <ToolTip text={t("tooltipFormatBold")}>
          <button
            type="button"
            tabIndex={currentFocusIndex == 2 ? 0 : -1}
            ref={(el) => {
              const index = "button-2" as unknown as number;
              if (el && itemsRef.current) {
                itemsRef.current[index] = el;
              }
            }}
            onClick={() => {
              editor.dispatchCommand(FORMAT_TEXT_COMMAND, "bold");
            }}
            className={
              "peer toolbar-item " + (isBold && editorHasFocus ? "active" : "")
            }
            aria-label="Format bold"
            aria-pressed={isBold}
            data-testid={`bold-button`}
          >
            <i aria-hidden="true" className="p-1 fa-solid fa-fas fa-bold"></i>
          </button>
        </ToolTip>

        <ToolTip text={t("tooltipFormatItalic")}>
          <button
            type="button"
            tabIndex={currentFocusIndex == 3 ? 0 : -1}
            ref={(el) => {
              const index = "button-3" as unknown as number;
              if (el && itemsRef.current) {
                itemsRef.current[index] = el;
              }
            }}
            onClick={() => {
              editor.dispatchCommand(FORMAT_TEXT_COMMAND, "italic");
            }}
            className={
              "peer toolbar-item " +
              (isItalic && editorHasFocus ? "active" : "")
            }
            aria-label="Format italic"
            aria-pressed={isItalic}
            data-testid={`italic-button`}
          >
            <i aria-hidden="true" className="p-1 fa-solid fa-fas fa-italic"></i>
          </button>
        </ToolTip>

        <ToolTip text={t("tooltipFormatBulletList")}>
          <button
            type="button"
            tabIndex={currentFocusIndex == 4 ? 0 : -1}
            ref={(el) => {
              const index = "button-4" as unknown as number;
              if (el && itemsRef.current) {
                itemsRef.current[index] = el;
              }
            }}
            onClick={formatBulletList}
            className={
              "peer toolbar-item " +
              (blockType === "bullet" && editorHasFocus ? "active" : "")
            }
            aria-label="Format bulleted list"
            aria-pressed={blockType === "bullet"}
            data-testid={`bullet-list-button`}
          >
            <i
              aria-hidden="true"
              className="p-1 fa-solid fa-fas fa-list-ul"
            ></i>
          </button>
        </ToolTip>

        <ToolTip text={t("tooltipFormatNumberedList")}>
          <button
            type="button"
            tabIndex={currentFocusIndex == 5 ? 0 : -1}
            ref={(el) => {
              const index = "button-5" as unknown as number;
              if (el && itemsRef.current) {
                itemsRef.current[index] = el;
              }
            }}
            onClick={formatNumberedList}
            className={
              "peer toolbar-item " +
              (blockType === "number" && editorHasFocus ? "active" : "")
            }
            aria-label="Format numbered list"
            aria-pressed={blockType === "number"}
            data-testid={`numbered-list-button`}
          >
            <i
              aria-hidden="true"
              className="p-1 fa-solid fa-fas fa-list-ol"
            ></i>
          </button>
        </ToolTip>

        <ToolTip text={t("tooltipInsertLink")}>
          <button
            type="button"
            tabIndex={currentFocusIndex == 6 ? 0 : -1}
            ref={(el) => {
              const index = "button-6" as unknown as number;
              if (el && itemsRef.current) {
                itemsRef.current[index] = el;
              }
            }}
            disabled={!isEditable}
            onClick={insertLink}
            className={
              "peer toolbar-item " + (isLink && editorHasFocus ? "active" : "")
            }
            aria-label="Insert link"
            aria-pressed={isLink}
            data-testid={`link-button`}
          >
            <i aria-hidden="true" className="p-1 fa-solid fa-fas fa-link"></i>
          </button>
        </ToolTip>

        <ToolTip text={t("tooltipInsertHR")}>
          <button
            type="button"
            tabIndex={currentFocusIndex == 6 ? 0 : -1}
            ref={(el) => {
              const index = "button-6" as unknown as number;
              if (el && itemsRef.current) {
                itemsRef.current[index] = el;
              }
            }}
            disabled={!isEditable}
            onClick={insertHR}
            className={"peer toolbar-item "}
            aria-label="Insert a horizontal rule"
            data-testid={`link-button`}
          >
            HR
          </button>
        </ToolTip>
      </div>
    </>
  );
};
