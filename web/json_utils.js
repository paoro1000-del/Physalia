"use strict";
(() => {
  window.assertNoDuplicateJsonKeys = function (source) {
    const MAX_JSON_DEPTH = 64;
    let index = 0;
    const whitespace = () => { while (/[\t\n\r ]/.test(source[index] || "")) index++; };
    function stringToken() {
      const start = index++;
      while (index < source.length) {
        if (source[index] === "\\") index += 2;
        else if (source[index++] === '"') return source.slice(start, index);
      }
      throw new Error("invalid JSON string");
    }
    function value(depth = 0) {
      whitespace();
      if (source[index] === "{") {
        if (depth >= MAX_JSON_DEPTH) throw new Error("JSON nesting too deep");
        index++;
        whitespace();
        const keys = new Set();
        if (source[index] === "}") { index++; return; }
        while (index < source.length) {
          whitespace();
          if (source[index] !== '"') throw new Error("invalid JSON object");
          const key = JSON.parse(stringToken()).toLowerCase();
          if (keys.has(key)) throw new Error("duplicate JSON key");
          keys.add(key);
          whitespace();
          if (source[index++] !== ":") throw new Error("invalid JSON object");
          value(depth + 1);
          whitespace();
          if (source[index] === "}") { index++; return; }
          if (source[index++] !== ",") throw new Error("invalid JSON object");
        }
        throw new Error("invalid JSON object");
      }
      if (source[index] === "[") {
        if (depth >= MAX_JSON_DEPTH) throw new Error("JSON nesting too deep");
        index++;
        whitespace();
        if (source[index] === "]") { index++; return; }
        while (index < source.length) {
          value(depth + 1);
          whitespace();
          if (source[index] === "]") { index++; return; }
          if (source[index++] !== ",") throw new Error("invalid JSON array");
        }
        throw new Error("invalid JSON array");
      }
      if (source[index] === '"') { stringToken(); return; }
      const start = index;
      while (index < source.length && !/[\t\n\r ,\]}]/.test(source[index])) index++;
      if (index === start) throw new Error("invalid JSON value");
    }
    value();
    whitespace();
    if (index !== source.length) throw new Error("invalid JSON trailing data");
  };
})();
