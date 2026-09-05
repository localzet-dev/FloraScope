# data

train 99955 / 39 aoi / 2010-24. test 57185 / 78 aoi / 3112 synthetic.

половина test полигонов новые: 39 overlap + 39 unseen. => id в модель категориально не пихаем.

primary подозрительно часто == sensor ndvi. проверили всё:

- train 30520/30520
- test known 17641/17641

правило: s2 если есть, иначе landsat, иначе modis.

это, пожалуй, самое полезное EDA-наблюдение. source-aware модель выросла отсюда.
