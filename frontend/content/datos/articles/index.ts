import type { ComponentType } from "react";
import ElTecho from "./el-techo-de-las-compras-directas";
import Benford from "./ley-de-benford-en-10-paises";
import Concentracion from "./el-1-por-ciento-que-se-lleva-casi-todo";
import Direccion from "./sobrecosto-o-subcosto";
import DosModelos from "./dos-modelos-un-contrato";

export const ARTICLES: Record<string, ComponentType> = {
  "el-techo-de-las-compras-directas": ElTecho,
  "ley-de-benford-en-10-paises": Benford,
  "el-1-por-ciento-que-se-lleva-casi-todo": Concentracion,
  "sobrecosto-o-subcosto": Direccion,
  "dos-modelos-un-contrato": DosModelos,
};
