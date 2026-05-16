import { defineConfig } from "eslint/config";
import next from "eslint-config-next";
import eslintConfigPrettier from "eslint-config-prettier";

const eslintConfig = defineConfig([...next, eslintConfigPrettier]);

export default eslintConfig;