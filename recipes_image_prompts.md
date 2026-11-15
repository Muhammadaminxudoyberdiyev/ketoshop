# Retsept rasmlari uchun promptlar (2026-11-13 dagi 15 ta retsept)

Har bir retsept (`recipes_content.py`) uchun bitta rasm kerak:
`webapp/recipes/<slug>.jpg`. Rasm qo'shilmaguncha retsept saytga ham, kanalga ham
chiqmaydi — navbatini kutadi (`recipes.py`, «Jadval»). Rasm qo'shilgach, keyingi
slotda o'zi chiqadi.

Qoidalar:

- Uslub eski 15 ta rasm bilan bir xil bo'lsin (masalan `webapp/recipes/bodom-noni.jpg`,
  `yashil-grechka-palov.jpg`, `keto-bulochka.jpg`), ularni reference sifatida bering.
- Fayl: JPG, 1400×1045 px (4:3, gorizontal), ~250–300 KB.
- Pastki o'ng burchakda o'sha dumaloq KETOSHOP logotipi (eski rasmlardagidek).
  Boshqa hech qanday yozuv, matn yoki watermark bo'lmasin.
- Rasmda ko'rinadigan hamma narsa retseptda bor. Retseptda yo'q narsa (non, boshqa
  meva, yong'oq va h.k.) rasmga qo'shilmaydi. Har bir prompt oxirida «Do not show»
  ro'yxati shuning uchun.
- Saytda va kanalda rasm ostida «📸 Rasm sun'iy intellekt yordamida yaratilgan»
  yozuvi chiqadi — rasm haqiqiy fotosuratdek bo'lsin, lekin yolg'on tafsilot qo'shilmasin.

Umumiy uslub (har bir promptga qo'shiladi):

> Photorealistic food photography, 4:3 landscape, 1400×1045. Bright soft natural
> daylight from the left, warm and airy, shallow depth of field. Light oak wooden
> table, a crumpled sage-green linen napkin, a few out-of-focus fresh green leaves
> in the background. Appetizing, home-made look, not glossy advertising. Round
> KETOSHOP logo badge in the bottom-right corner exactly as in the reference
> photos. No other text, no hands, no people.

---

## keto-somsa

- Fayl: `webapp/recipes/keto-somsa.jpg`
- Retsept: Go'shtli keto somsa

Prompt:

> Eight golden-brown triangular keto samsa pastries on a light oak board lined with
> parchment. The dough is smooth almond-flour-and-mozzarella dough (not flaky wheat
> puff pastry), brushed with egg yolk and sprinkled with black nigella seeds and
> white sesame seeds. One samsa in the front is broken open, showing a juicy filling
> of minced lamb with finely chopped onion and small cubes of rendered tail fat,
> a little steam rising. Small ceramic bowl of black nigella seeds and a small bowl
> of white sesame on the side, half an onion. Common style above.

Do not show: bread, tomatoes, salad, herbs on the plate, sauces, tandoor.

## tungi-suli-botqa

- Fayl: `webapp/recipes/tungi-suli-botqa.jpg`
- Retsept: Bankada tungi suli bo'tqasi

Prompt:

> Two glass jars of overnight oats on a light oak table: creamy soaked rolled oats
> with visible chia seeds, a layer of white natural yogurt, topped with fresh
> raspberries and blueberries and a light dusting of ground cinnamon. A long spoon
> in one jar. A small bowl of rolled oats and a small bowl of chia seeds beside
> them, a small jug of milk. Morning light. Common style above.

Do not show: banana, nuts, honey, granola, mint, chocolate.

## lasos-kotlet

- Fayl: `webapp/recipes/lasos-kotlet.jpg`
- Retsept: Lasos baliqli keto kotletlar

Prompt:

> A white ceramic plate with five golden pan-fried salmon patties (6 cm, 1.5 cm thick,
> crisp golden crust, flecks of dill and onion visible at the edge of one cut patty
> showing pink-beige flaked salmon inside). A small bowl of thick white yogurt sauce
> with finely diced cucumber and a little garlic, cucumber slices and two lemon
> wedges on the plate, a few dill sprigs. In the background an open glass jar of
> canned salmon. Common style above.

Do not show: potatoes, rice, bread, tomatoes, lettuce, tartar sauce, fresh raw fish.

## dubay-shokolad

- Fayl: `webapp/recipes/dubay-shokolad.jpg`
- Retsept: Uyda shakarsiz «Dubay shokoladi»

Prompt:

> A homemade sugar-free "Dubai chocolate" bar on parchment on a light oak board,
> broken/cut in half to show the cross-section: a glossy dark chocolate shell
> around a thick bright pistachio-green cream packed with crispy golden toasted
> coconut shreds. Several cut squares stacked in front, the green filling clearly
> visible. A small open jar of green pistachio paste with a spoon, a few pieces of
> dark chocolate and a scattering of toasted coconut chips beside it. Common style
> above.

Do not show: whole pistachios or any other nuts, kataifi pastry, gold leaf,
brand wrappers, milk.

## devzira-mastava

- Fayl: `webapp/recipes/devzira-mastava.jpg`
- Retsept: Devzira guruchli mastava

Prompt:

> A traditional Uzbek ceramic kosa (bowl) of mastava soup: clear reddish-orange
> tomato broth with cubes of beef, diced carrot, red bell pepper and tomato, and
> visible reddish-brown devzira rice grains. A spoonful of thick white qatiq
> (yogurt) on top, sprinkled with chopped dill and coriander. A second kosa in the
> background, a small bowl of qatiq, a bunch of dill and coriander, a garlic bulb.
> Common style above.

Do not show: bread or non, potatoes, noodles, white rice, lemon.

## javdar-non

- Fayl: `webapp/recipes/javdar-non.jpg`
- Retsept: Javdar unli solodli PP non

Prompt:

> A dark brown rye-and-malt loaf baked in a rectangular tin (Borodinsky style),
> top sprinkled with crushed coriander seeds, set on a light oak cutting board.
> Four slices cut in front showing a dense, moist, dark chocolate-brown crumb.
> A small bowl of rye flour, a small bowl of dark fermented malt powder and a few
> coriander seeds scattered on the board. Common style above.

Do not show: butter, cheese, sausage, seeds other than coriander, sesame, white bread.

## keto-manti

- Fayl: `webapp/recipes/keto-manti.jpg`
- Retsept: Qovoq va go'shtli keto manti

Prompt:

> A wide white plate of steamed keto manti dumplings: classic pinched Uzbek manti
> shape, the dough slightly beige and matte (white flax flour and psyllium, not
> shiny white wheat dough). One manti cut open, showing juicy minced meat with
> small orange cubes of pumpkin and onion. A small bowl of thick white qatiq
> (yogurt) dusted with ground black pepper. In the background a tier of an
> aluminium manti steamer (qasqon) and a wedge of peeled orange pumpkin.
> Common style above.

Do not show: tomato sauce, herbs on top, bread, potatoes, salad.

## noxat-quymoq

- Fayl: `webapp/recipes/noxat-quymoq.jpg`
- Retsept: No'xat unidan sabzavotli quymoq

Prompt:

> A stack of golden, slightly thick savory chickpea-flour fritters on a ceramic
> plate, warm yellow from turmeric, with visible bits of diced tomato, onion, red
> bell pepper and green coriander. A small bowl of thick white qatiq (yogurt)
> garnished with chopped coriander. A small bowl of pale-yellow chickpea flour and
> a few coriander sprigs on the side. Common style above.

Do not show: eggs, whole chickpeas, cheese, bread, lemon.

## yeryongoq-pechenye

- Fayl: `webapp/recipes/yeryongoq-pechenye.jpg`
- Retsept: Yeryong'oq pastali keto pechenye

Prompt:

> Twelve round peanut-butter cookies with the classic criss-cross fork pattern,
> golden edges and soft centres, on parchment paper on a baking tray / light oak
> board. One cookie broken in half showing a soft, dense inside. A small open jar of
> smooth peanut paste with a spoon and a small bowl of white granulated sweetener
> beside it. Common style above.

Do not show: whole peanuts, chocolate, milk, jam, flour.

## qovoq-krem-shorva

- Fayl: `webapp/recipes/qovoq-krem-shorva.jpg`
- Retsept: Kokos slivkali qovoq krem-sho'rvasi

Prompt:

> Two ceramic bowls of smooth, velvety bright-orange pumpkin cream soup, each with
> a white swirl of coconut cream, a sprinkle of toasted green pumpkin seeds and a
> few parsley leaves on top. Behind them half a peeled orange pumpkin, a small jug
> of coconut cream, two garlic cloves. Common style above.

Do not show: bread, croutons, whole coconut, chili, cheese.

## grechka-lagmon

- Fayl: `webapp/recipes/grechka-lagmon.jpg`
- Retsept: Grechka vermishelidan PP lag'mon

Prompt:

> A deep ceramic bowl of Uzbek lagman made with thin brown buckwheat vermicelli
> noodles, topped with a thick vegetable-and-beef sauce (vaju): julienned beef,
> strips of red and green bell pepper, carrot, green radish and tomato, finished
> with chopped fresh coriander, a fork on the side. Beside it a red and
> a green bell pepper, a garlic bulb, a small bunch of coriander. Common style above.

Do not show: white wheat noodles, eggs, bread, soy sauce bottle, chili peppers.

## olmali-sharlotka

- Fayl: `webapp/recipes/olmali-sharlotka.jpg`
- Retsept: Suli unidan olmali PP sharlotka

Prompt:

> A round, golden apple charlotte (sharlotka) made with oat flour, about 22 cm, on
> a light ceramic plate; thin apple slices baked into the top, a light dusting of
> ground cinnamon. One wedge cut out and placed in front, showing an airy, light
> beige sponge with apple pieces inside. Two whole fresh apples, a small bowl of
> ground cinnamon and a cup of tea beside it. Common style above.

Do not show: powdered sugar, cream, ice cream, nuts, berries, cinnamon sticks.

## bulgur-salat

- Fayl: `webapp/recipes/bulgur-salat.jpg`
- Retsept: Bulgurli ko'katli PP salat

Prompt:

> A wide ceramic bowl of fresh bulgur salad: lots of very finely chopped parsley and
> mint, spring onion, small cubes of tomato and cucumber mixed with fluffy bulgur,
> glistening with olive oil. Lemon wedges on top. Beside it half a lemon, a small
> bottle of olive oil, a bunch of parsley and a few mint leaves. Common style above.

Do not show: feta or other cheese, olives, chickpeas, bread, meat.

## grechka-blinchik

- Fayl: `webapp/recipes/grechka-blinchik.jpg`
- Retsept: Grechka unidan tvorogli blinchiklar

Prompt:

> Thin, brown, lacy buckwheat crepes folded into envelopes, lightly browned, on a
> white plate; one cut open showing a white creamy cottage-cheese (tvorog) filling.
> A dollop of sour cream (qaymoq) beside them, a stack of plain crepes in the
> background, a small bowl of buckwheat flour. Common style above.

Do not show: berries, jam, honey, syrup, fruit, mint.

## zogora-non

- Fayl: `webapp/recipes/zogora-non.jpg`
- Retsept: Makkajo'xori unidan zog'ora non

Prompt:

> A round Uzbek cornbread, zog'ora non, baked in a black cast-iron skillet: golden
> yellow, slightly cracked top with fingertip dimples, glistening with a little
> melted ghee. Cut into wedges, one wedge pulled out showing a moist yellow crumb.
> A ceramic bowl of thick white qatiq (yogurt) and a small bowl of yellow corn flour
> beside it. Common style above.

Do not show: corn cobs, butter blocks, honey, herbs, nigella seeds, soup.
