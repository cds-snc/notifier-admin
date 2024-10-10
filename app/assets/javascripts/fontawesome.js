/**
 * This file loads in font awesome for use in Notify
 * We only load the icons we use to keep the bundle size down. To add an icon:
 * - import if from @fortawesome/free-solid-svg-icons
 * - include it in the library.add call
 */
import { config } from "@fortawesome/fontawesome-svg-core";
import { library, dom } from "@fortawesome/fontawesome-svg-core";
import { faCheck } from "@fortawesome/free-solid-svg-icons/faCheck";
import { faArrowUpRightFromSquare } from "@fortawesome/free-solid-svg-icons/faArrowUpRightFromSquare";
import { faPlus } from "@fortawesome/free-solid-svg-icons/faPlus";
import { faArrowRight } from "@fortawesome/free-solid-svg-icons/faArrowRight";
import { faAngleDown } from "@fortawesome/free-solid-svg-icons/faAngleDown";
import { faCircleQuestion } from "@fortawesome/free-solid-svg-icons/faCircleQuestion";
import { faTriangleExclamation } from "@fortawesome/free-solid-svg-icons/faTriangleExclamation";
import { faCircleExclamation } from "@fortawesome/free-solid-svg-icons/faCircleExclamation";
import { faBold } from "@fortawesome/free-solid-svg-icons/faBold";
import { faItalic } from "@fortawesome/free-solid-svg-icons/faItalic";
import { faListOl } from "@fortawesome/free-solid-svg-icons/faListOl";
import { faListUl } from "@fortawesome/free-solid-svg-icons/faListUl";
import { faHeading } from "@fortawesome/free-solid-svg-icons/faHeading";
import { fa1 } from "@fortawesome/free-solid-svg-icons/fa1";
import { fa2 } from "@fortawesome/free-solid-svg-icons/fa2";
import { fa3 } from "@fortawesome/free-solid-svg-icons/fa3";
import { faLink } from "@fortawesome/free-solid-svg-icons/faLink";
import { faPencil } from "@fortawesome/free-solid-svg-icons/faPencil";
import { faGripLines } from "@fortawesome/free-solid-svg-icons/faGripLines";
import { faInfoCircle } from "@fortawesome/free-solid-svg-icons";
import { faXmark } from "@fortawesome/free-solid-svg-icons/faXMark";
import { faTag } from "@fortawesome/free-solid-svg-icons/faTag";

let FontAwesomeIconLoader = () => {
  config.autoAddCss = false;
  library.add([
    faCheck,
    faArrowUpRightFromSquare,
    faPlus,
    faArrowRight,
    faAngleDown,
    faCircleQuestion,
    faTriangleExclamation,
    faCircleExclamation,
    faBold,
    faItalic,
    faListOl,
    faListUl,
    faHeading,
    fa1,
    fa2,
    fa3,
    faLink,
    faPencil,
    faGripLines,
    faInfoCircle,
    faXmark,
    faTag,
  ]);
  dom.watch();
};

export default FontAwesomeIconLoader;
