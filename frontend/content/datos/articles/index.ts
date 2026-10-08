import type { ComponentType } from "react";
import ElTecho from "./el-techo-de-las-compras-directas";
import Benford from "./ley-de-benford-en-10-paises";
import Direccion from "./sobrecosto-o-subcosto";
import FinDeSemana from "./contratos-en-fin-de-semana";
import Diciembre from "./el-efecto-diciembre";

export const ARTICLES: Record<string, ComponentType> = {
  "el-techo-de-las-compras-directas": ElTecho,
  "ley-de-benford-en-10-paises": Benford,
  "sobrecosto-o-subcosto": Direccion,
  "contratos-en-fin-de-semana": FinDeSemana,
  "el-efecto-diciembre": Diciembre,
};
