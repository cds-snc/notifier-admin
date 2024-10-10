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
  $getPreviousSelection,
  $isRangeSelection,
  SELECTION_CHANGE_COMMAND,
  $createParagraphNode,
  $setSelection,
} from "lexical";

import { INSERT_HORIZONTAL_RULE_COMMAND } from "@lexical/react/LexicalHorizontalRuleNode";

import { $wrapNodes, $moveCaretSelection } from "@lexical/selection";
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
  tooltipFormatH1: "Heading level 1",
  tooltipFormatH2: "Heading level 2",
  tooltipFormatBold: "Bold (⌘B)",
  tooltipFormatItalic: "Italic (⌘I)",
  tooltipFormatBulletList: "Bulleted list",
  tooltipFormatNumberedList: "Numbered list",
  tooltipInsertLink: "Insert link",
  tooltipInsertHR: "Insert divider",
};

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
  const [formattingInstruction, setformattingInstruction] = useState("");

  const insertLink = useCallback(() => {
    if (!isLink) {
      editor.dispatchCommand(TOGGLE_LINK_COMMAND, sanitizeUrl("https://"));
      // announce to screen readers that formatting has been applied/removed
      a11y_announce("Link", "inserted");
    } else {
      editor.dispatchCommand(TOGGLE_LINK_COMMAND, null);
      a11y_announce("Link", "removed");
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
    { id: 8, txt: "hr" },
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

  /* Announce formatting applied to screen reader users */
  const a11y_announce = (
    formatting: string,
    action: "applied" | "removed" | "inserted",
  ) => {
    setformattingInstruction(`${formatting} ${action}`);
  };

  /**
   * Removes the last character from the selection to
   * avoid a bug primarily with keyboard selection that would apply
   * formatting to the line above or below the current selection,
   * depending on which direction the selection was made from
   */
  const removeLastCharacterFromSelection = () => {
    editor.update(() => {
      const selection = $getSelection();
      if ($isRangeSelection(selection)) {
        $moveCaretSelection(
          selection,
          true,
          !selection.isBackward(),
          "character",
        );
      }
    });
  };

  /**
   * Undoes the last selection change
   */
  const undoSelectionChange = () => {
    editor.update(() => {
      const prevSelection = $getPreviousSelection();
      $setSelection(prevSelection);
    });
  };
  const formatHeading = (level: HeadingTagType) => {
    if (blockType === level) {
      formatParagraph();

      // announce to screen readers that formatting has been applied/removed
      a11y_announce(level, "removed");
    }

    if (blockType !== level) {
      editor.update(() => {
        const selection = $getSelection();
        if ($isRangeSelection(selection)) {
          $wrapNodes(selection, () => $createHeadingNode(level));
        }
        // announce to screen readers that formatting has been applied/removed
        a11y_announce(level, "applied");
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

    // announce to screen readers that formatting has been applied/removed
    a11y_announce("Paragraph", "applied");
  };

  const formatBulletList = (evt: React.MouseEvent<HTMLButtonElement>) => {
    evt.preventDefault();
    if (blockType !== "bullet") {
      removeLastCharacterFromSelection();
      removeLastCharacterFromSelection();
      editor.dispatchCommand(INSERT_UNORDERED_LIST_COMMAND, undefined);
      undoSelectionChange();
      return;
    }
    editor.dispatchCommand(REMOVE_LIST_COMMAND, undefined);

    // announce to screen readers that formatting has been applied/removed
    a11y_announce("Bulleted list", "removed");
  };

  const formatNumberedList = (evt: React.MouseEvent<HTMLButtonElement>) => {
    evt.preventDefault();
    if (blockType !== "number") {
      removeLastCharacterFromSelection();
      removeLastCharacterFromSelection();
      editor.dispatchCommand(INSERT_ORDERED_LIST_COMMAND, undefined);
      undoSelectionChange();
      return;
    }
    editor.dispatchCommand(REMOVE_LIST_COMMAND, undefined);

    // announce to screen readers that formatting has been applied/removed
    a11y_announce("Numbered list", "removed");
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

  // customize shortcuts to OS
  var shortcutKey = window.navigator.userAgent.includes("Mac") ? "⌘" : "ctrl";
  const tooltipFormatBold = `Bold (${shortcutKey}+B)`;
  const tooltipFormatItalic = `Italic (${shortcutKey}+I)`;

  // help-button focus
  const handleFocus = (event: any) => {
    // if relatedTarget is '#help-button', tab again
    if (event.relatedTarget.dataset.lexicalEditor) {
      document
        .querySelector<HTMLButtonElement>(
          '#toolbar-container button[tabindex="0"]',
        )
        ?.focus();
    }
  };

  const editorHasFocus = useEditorFocus();

  // @ts-expect-error
  window.editor = editor;
  // @ts-expect-error
  window.moveSelection = $moveCaretSelection;

  // window.getSelection = $getSelection;

  return (
    <>
      <div
        className="toolbar-container"
        role="toolbar"
        aria-controls={editorId}
        onKeyDown={handleNav}
        data-testid="toolbar"
      >
        <div className="toolbar-inner">
          <div className="flex">
            <div className="flex-grow" id="toolbar-container">
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
                  <i
                    aria-hidden="true"
                    className="p-1 fa-solid fa-fas fa-1"
                  ></i>
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
                  <i
                    aria-hidden="true"
                    className="p-1 fa-solid fa-fas fa-2"
                  ></i>
                </button>
              </ToolTip>

              <ToolTip text={tooltipFormatBold}>
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

                    // announce to screen readers that formatting has been applied/removed
                    const action = isBold ? "removed" : "applied";
                    a11y_announce("Bold", action);
                  }}
                  className={
                    "peer toolbar-item " +
                    (isBold && editorHasFocus ? "active" : "")
                  }
                  aria-label="Format bold"
                  aria-pressed={isBold}
                  data-testid={`bold-button`}
                >
                  <i
                    aria-hidden="true"
                    className="p-1 fa-solid fa-fas fa-bold"
                  ></i>
                </button>
              </ToolTip>

              <ToolTip text={tooltipFormatItalic}>
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

                    // announce to screen readers that formatting has been applied/removed
                    const action = isItalic ? "removed" : "applied";
                    a11y_announce("Italic", action);
                  }}
                  className={
                    "peer toolbar-item " +
                    (isItalic && editorHasFocus ? "active" : "")
                  }
                  aria-label="Format italic"
                  aria-pressed={isItalic}
                  data-testid={`italic-button`}
                >
                  <i
                    aria-hidden="true"
                    className="p-1 fa-solid fa-fas fa-italic"
                  ></i>
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
                    "peer toolbar-item " +
                    (isLink && editorHasFocus ? "active" : "")
                  }
                  aria-label="Insert link"
                  aria-pressed={isLink}
                  data-testid={`link-button`}
                >
                  <i
                    aria-hidden="true"
                    className="p-1 fa-solid fa-fas fa-link"
                  ></i>
                </button>
              </ToolTip>

              <ToolTip text={t("tooltipInsertHR")}>
                <button
                  type="button"
                  tabIndex={currentFocusIndex == 7 ? 0 : -1}
                  ref={(el) => {
                    const index = "button-7" as unknown as number;
                    if (el && itemsRef.current) {
                      itemsRef.current[index] = el;
                    }
                  }}
                  disabled={!isEditable}
                  onClick={insertHR}
                  className={"peer toolbar-item "}
                  aria-label="Insert a divider"
                  data-testid={`link-button`}
                >
                  <i
                    aria-hidden="true"
                    className="p-1 fa-solid fa-fas fa-grip-lines"
                  ></i>
                </button>
              </ToolTip>
            </div>
            <div className="flex-grow-0">
              <ToolTip text="Help">
                <a
                  id="help-button"
                  onFocus={handleFocus}
                  aria-label="Help"
                  className="btn text-xs inline-block flex"
                  href="#open-modal"
                >
                  <i
                    aria-hidden="true"
                    className="p-1 fa-solid fa-fas fa-circle-question mr-1"
                  ></i>
                </a>
              </ToolTip>
            </div>
          </div>
        </div>
        <div id="open-modal" className="modal-window">
          <div>
            <a href="#help-button" title="Close" className="modal-close">
              Close
            </a>
            <h1 className="flex items-center">
              <span className="inline-block mb-1 font-bold">Help</span>
            </h1>
            <h2 className="mb-4">Keyboard shortcuts</h2>
            <ul className="list-disc ml-10 text-sm">
              <li className="mb-2">
                From anywhere in the editor window, press <kbd>shift</kbd>+
                <kbd>tab</kbd> to focus on the toolbar{" "}
              </li>
              <li className="mb-2">
                On the toolbar use the <kbd>←</kbd> and <kbd>→</kbd> arrow keys
                to choose an option
              </li>
              {/* <li>Note: You can also use markdown for formatting</li> */}
            </ul>
            <h2 className="mt-6 mb-4">Formatting options</h2>
            <ul className="list-disc ml-10 text-sm">
              <li className="mb-2">
                Text formatting: heading level 1, heading level 2, bold, italics
              </li>
              <li className="mb-2">
                List formatting: bulleted lists, numbered lists
              </li>
              <li className="mb-2">Other: hyperlinks, dividers</li>
              <li className="mb-2">Note: You can also use markdown</li>
            </ul>
          </div>
        </div>
      </div>
      <div role="region" className="sr-only" aria-live="polite">
        <span>{formattingInstruction}</span>
      </div>
    </>
  );
};
