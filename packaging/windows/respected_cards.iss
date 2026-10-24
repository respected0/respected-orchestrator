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
  CardH[Group] := ScaleY(CardHeight);
  CardSpace[Group] := ScaleY(CardGap);
end;

// call right after NewCardPage for a long list: shorter cards, titles only (pass '' as the help text)
procedure CompactCards(Group: Integer);
begin
  CardH[Group] := ScaleY(42);
  CardSpace[Group] := ScaleY(6);
end;

procedure AddCard(Page: TWizardPage; Group: Integer; Glyph, Title, Help: String; Checked: Boolean);
var
  Item, Slot, Tag, TitleTop, HelpTop: Integer;
  Icon, Name, Note: TNewStaticText;
begin
  Item := CardCount[Group];
  Slot := Group * CardMax + Item;
  Tag := Slot;
  CardCount[Group] := Item + 1;
  // the title and the help text are centred as one block; the choice button and the icon sit on the card's centre line
  if Help = '' then TitleTop := (CardH[Group] - ScaleY(18)) div 2
  else TitleTop := (CardH[Group] - ScaleY(36)) div 2;
  HelpTop := TitleTop + ScaleY(20);

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

  // the real radio button / check box is only the round or square mark: its caption (the title, kept for keyboard and screen
  // readers) is cut off by the control's width and the visible title is the label next to the icon
  if CardMulti[Group] then begin
    CardCheck[Slot] := TNewCheckBox.Create(Page);
    CardCheck[Slot].Parent := CardInner[Slot];
    CardCheck[Slot].SetBounds(ScaleX(14), (CardH[Group] - ScaleY(20)) div 2, ScaleX(17), ScaleY(20));
    CardCheck[Slot].Caption := Title;
    CardCheck[Slot].Checked := Checked;
    CardCheck[Slot].Tag := Tag;
    CardCheck[Slot].OnClick := @CardClick;
  end else begin
    CardRadio[Slot] := TNewRadioButton.Create(Page);
    CardRadio[Slot].Parent := CardInner[Slot];
    CardRadio[Slot].SetBounds(ScaleX(14), (CardH[Group] - ScaleY(20)) div 2, ScaleX(17), ScaleY(20));
    CardRadio[Slot].Caption := Title;
    CardRadio[Slot].Checked := Checked;
    CardRadio[Slot].Tag := Tag;
    CardRadio[Slot].OnClick := @CardClick;
  end;

  Icon := TNewStaticText.Create(Page);
  Icon.Parent := CardInner[Slot];
  Icon.AutoSize := False;
  Icon.SetBounds(ScaleX(42), (CardH[Group] - ScaleY(22)) div 2, ScaleX(28), ScaleY(22));
  Icon.Font.Name := 'Segoe MDL2 Assets';
  Icon.Font.Size := 16;
  Icon.Font.Color := CardAccent;
  Icon.Caption := Glyph;
  Icon.Tag := Tag;
  Icon.OnClick := @CardClick;

  Name := TNewStaticText.Create(Page);
  Name.Parent := CardInner[Slot];
  Name.AutoSize := False;
  Name.SetBounds(ScaleX(80), TitleTop, Page.SurfaceWidth - ScaleX(80) - ScaleX(14), ScaleY(18));
  Name.Font.Style := [fsBold];
  Name.Caption := Title;
  Name.Tag := Tag;
  Name.OnClick := @CardClick;

  if Help <> '' then begin
    Note := TNewStaticText.Create(Page);
    Note.Parent := CardInner[Slot];
    Note.AutoSize := False;
    Note.WordWrap := True;
    Note.SetBounds(ScaleX(80), HelpTop, Page.SurfaceWidth - ScaleX(80) - ScaleX(14), CardH[Group] - HelpTop - ScaleY(4));
    Note.Font.Color := $8E7C6E;  // #6E7C8E
    Note.Caption := Help;
    Note.Tag := Tag;
    Note.OnClick := @CardClick;
  end;

  CardPaint(Group);
end;

// The info pages (beta notice, what's new) carry a click label that only leaves a gap above the text: hide it and let the
// text box start right under the header.
procedure TidyInfoPages;
var
  Gap: Integer;
begin
  // the inner pages start a little below the header: close most of that gap so the content sits close under the title
  Gap := WizardForm.InnerNotebook.Top - WizardForm.MainPanel.Height;
  if Gap > 0 then begin
    // not all of it: a two-line description would otherwise touch the content
    WizardForm.InnerNotebook.Top := WizardForm.MainPanel.Height + Gap div 2;
    WizardForm.InnerNotebook.Height := WizardForm.InnerNotebook.Height + Gap - Gap div 2;
  end;
  // no logo in the header of the inner pages (the welcome and finish pages carry it): the title and text take its room
  WizardForm.WizardSmallBitmapImage.Visible := False;
  WizardForm.PageNameLabel.Width := WizardForm.MainPanel.Width - WizardForm.PageNameLabel.Left - ScaleX(16);
  WizardForm.PageDescriptionLabel.Width := WizardForm.MainPanel.Width - WizardForm.PageDescriptionLabel.Left - ScaleX(16);
  // the page title sits a few pixels left of its description and of the content under it: one column
  WizardForm.PageNameLabel.Left := WizardForm.PageDescriptionLabel.Left;
  WizardForm.InfoBeforeClickLabel.Visible := False;
  WizardForm.InfoBeforeMemo.SetBounds(0, 0, WizardForm.InfoBeforePage.Width, WizardForm.InfoBeforePage.Height);
  WizardForm.InfoAfterClickLabel.Visible := False;
  WizardForm.InfoAfterMemo.SetBounds(0, 0, WizardForm.InfoAfterPage.Width, WizardForm.InfoAfterPage.Height);
end;

// nothing to go back to once the installation is over (the what's-new page comes before the finish page)
// each installer defines this for its own pages
procedure ProductPageChanged(CurPageID: Integer); forward;

var
  InstallFailed: Boolean;  // set by the installer's FailInstall: its last page must not claim success

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpFinished then begin
    WizardForm.BackButton.Visible := False;
    if InstallFailed then begin
      WizardForm.FinishedHeadingLabel.Caption := 'Kurulum tamamlanamadı';
      WizardForm.FinishedLabel.Caption := 'Ürün kendi değişikliklerini geri aldı. Kurucuyu yeniden çalıştırabilirsiniz.';
    end;
  end;
  ProductPageChanged(CurPageID);
end;

procedure ExitProcess(ExitCode: Cardinal); external 'ExitProcess@kernel32.dll stdcall';

// Abort in the post-install step leaves Inno's own exit code at 0: a script or the Hub must still see that the install failed
procedure DeinitializeSetup();
begin
  if InstallFailed then ExitProcess(8);
end;
