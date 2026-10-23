// Card-style choice pages for the Respected installers (an icon, a title and one line of help per option) instead of a plain
// radio list. Included from the [Code] section: #include "respected_cards.iss". Each option still holds a real radio button or
// check box (keyboard and screen reader work); the card only adds the frame, the icon and the help text.
//   NewCardPage(Group, AfterID, Caption, Description, Multi)   Group 0..3, one page per group
//   AddCard(Page, Group, Glyph, Title, Help, Checked)
//   CardSelectedIndex(Group) / CardChecked(Group, Item) / SetCardChecked(Group, Item, Value)
// Glyphs are Segoe MDL2 Assets (Windows 10 and 11).

const
  CardAccent = $F0832F;     // BGR of #2F83F0
  CardFrame = $E6DCD2;      // #D2DCE6
  CardPaper = $FFFFFF;
  CardPicked = $FFF6EE;     // #EEF6FF
  CardHeight = 62;
  CardGap = 8;
  CardMax = 8;

var
  CardOuter, CardInner: array[0..31] of TPanel;
  CardRadio: array[0..31] of TNewRadioButton;
  CardCheck: array[0..31] of TNewCheckBox;
  CardCount: array[0..3] of Integer;
  CardMulti: array[0..3] of Boolean;
  CardH, CardSpace: array[0..3] of Integer;

function CardIsOn(Group, Item: Integer): Boolean;
begin
  if CardMulti[Group] then Result := CardCheck[Group * CardMax + Item].Checked
  else Result := CardRadio[Group * CardMax + Item].Checked;
end;

procedure CardPaint(Group: Integer);
var
  I, Slot, Edge: Integer;
begin
  for I := 0 to CardCount[Group] - 1 do begin
    Slot := Group * CardMax + I;
    if CardIsOn(Group, I) then begin
      CardOuter[Slot].Color := CardAccent; CardInner[Slot].Color := CardPicked; Edge := 2;
    end else begin
      CardOuter[Slot].Color := CardFrame; CardInner[Slot].Color := CardPaper; Edge := 1;
    end;
    CardInner[Slot].SetBounds(Edge, Edge, CardOuter[Slot].Width - 2 * Edge, CardOuter[Slot].Height - 2 * Edge);
  end;
end;

procedure SetCardChecked(Group, Item: Integer; Value: Boolean);
var
  I: Integer;
begin
  if CardMulti[Group] then CardCheck[Group * CardMax + Item].Checked := Value
  else begin
    for I := 0 to CardCount[Group] - 1 do CardRadio[Group * CardMax + I].Checked := (I = Item) and Value;
  end;
  CardPaint(Group);
end;

procedure CardClick(Sender: TObject);
var
  Group, Item: Integer;
begin
  Group := TComponent(Sender).Tag div CardMax;
  Item := TComponent(Sender).Tag mod CardMax;
  if CardMulti[Group] then begin
    // a click on the check box itself already toggled it; a click anywhere else on the card toggles it here
    if not (Sender is TNewCheckBox) then CardCheck[Group * CardMax + Item].Checked := not CardCheck[Group * CardMax + Item].Checked;
    CardPaint(Group);
  end else
    SetCardChecked(Group, Item, True);
end;

function CardSelectedIndex(Group: Integer): Integer;
var
  I: Integer;
begin
  Result := 0;
  for I := 0 to CardCount[Group] - 1 do
    if CardRadio[Group * CardMax + I].Checked then Result := I;
end;

function CardChecked(Group, Item: Integer): Boolean;
begin
  Result := CardIsOn(Group, Item);
end;

function NewCardPage(Group, AfterID: Integer; Caption, Description: String; Multi: Boolean): TWizardPage;
begin
  Result := CreateCustomPage(AfterID, Caption, Description);
  CardCount[Group] := 0;
  CardMulti[Group] := Multi;
  CardH[Group] := CardHeight;
  CardSpace[Group] := CardGap;
end;

// call right after NewCardPage for a long list: shorter cards, titles only (pass '' as the help text)
procedure CompactCards(Group: Integer);
begin
  CardH[Group] := 42;
  CardSpace[Group] := 6;
end;

procedure AddCard(Page: TWizardPage; Group: Integer; Glyph, Title, Help: String; Checked: Boolean);
var
  Item, Slot, Tag, TitleTop, IconTop: Integer;
  Icon, Note: TNewStaticText;
begin
  Item := CardCount[Group];
  Slot := Group * CardMax + Item;
  if Help = '' then begin TitleTop := (CardH[Group] - 20) div 2; IconTop := (CardH[Group] - 22) div 2; end
  else begin TitleTop := 9; IconTop := (CardH[Group] - 32) div 2; end;
  Tag := Slot;
  CardCount[Group] := Item + 1;

  CardOuter[Slot] := TPanel.Create(Page);
  CardOuter[Slot].Parent := Page.Surface;
  CardOuter[Slot].BevelOuter := bvNone;
  CardOuter[Slot].ParentBackground := False;
  CardOuter[Slot].SetBounds(0, Item * (CardH[Group] + CardSpace[Group]), Page.SurfaceWidth, CardH[Group]);
  CardOuter[Slot].Tag := Tag;
  CardOuter[Slot].OnClick := @CardClick;

  CardInner[Slot] := TPanel.Create(Page);
  CardInner[Slot].Parent := CardOuter[Slot];
  CardInner[Slot].BevelOuter := bvNone;
  CardInner[Slot].ParentBackground := False;
  CardInner[Slot].Tag := Tag;
  CardInner[Slot].OnClick := @CardClick;

  Icon := TNewStaticText.Create(Page);
  Icon.Parent := CardInner[Slot];
  Icon.AutoSize := False;
  Icon.SetBounds(14, IconTop, 28, 32);
  Icon.Font.Name := 'Segoe MDL2 Assets';
  Icon.Font.Size := 16;
  Icon.Font.Color := CardAccent;
  Icon.Caption := Glyph;
  Icon.Tag := Tag;
  Icon.OnClick := @CardClick;

  if CardMulti[Group] then begin
    CardCheck[Slot] := TNewCheckBox.Create(Page);
    CardCheck[Slot].Parent := CardInner[Slot];
    CardCheck[Slot].SetBounds(52, TitleTop, Page.SurfaceWidth - 52 - 14, 20);
    CardCheck[Slot].Caption := Title;
    CardCheck[Slot].Font.Style := [fsBold];
    CardCheck[Slot].Checked := Checked;
    CardCheck[Slot].Tag := Tag;
    CardCheck[Slot].OnClick := @CardClick;
  end else begin
    CardRadio[Slot] := TNewRadioButton.Create(Page);
    CardRadio[Slot].Parent := CardInner[Slot];
    CardRadio[Slot].SetBounds(52, TitleTop, Page.SurfaceWidth - 52 - 14, 20);
    CardRadio[Slot].Caption := Title;
    CardRadio[Slot].Font.Style := [fsBold];
    CardRadio[Slot].Checked := Checked;
    CardRadio[Slot].Tag := Tag;
    CardRadio[Slot].OnClick := @CardClick;
  end;

  if Help <> '' then begin
    Note := TNewStaticText.Create(Page);
    Note.Parent := CardInner[Slot];
    Note.AutoSize := False;
    Note.WordWrap := True;
    Note.SetBounds(52 + 19, 31, Page.SurfaceWidth - 52 - 19 - 14, CardH[Group] - 31 - 6);
    Note.Font.Color := $8E7C6E;  // #6E7C8E
    Note.Caption := Help;
    Note.Tag := Tag;
    Note.OnClick := @CardClick;

  end;

  CardPaint(Group);
end;
