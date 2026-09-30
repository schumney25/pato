/*---------------------------------------------------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     |
    \\  /    A nd           | Copyright (C) 2011-2016 OpenFOAM Foundation
     \\/     M anipulation  |
-------------------------------------------------------------------------------
License
    This file is part of OpenFOAM.

    OpenFOAM is free software: you can redistribute it and/or modify it
    under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    OpenFOAM is distributed in the hope that it will be useful, but WITHOUT
    ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
    FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
    for more details.

    You should have received a copy of the GNU General Public License
    along with OpenFOAM.  If not, see <http://www.gnu.org/licenses/>.

\*---------------------------------------------------------------------------*/

#include "HeatFluxRecessionFvPatchScalarField.H"
#include "addToRunTimeSelectionTable.H"
#include "fvPatchFieldMapper.H"
#include "volFields.H"

// * * * * * * * * * * * * * * * * Constructors  * * * * * * * * * * * * * * //

Foam::HeatFluxRecessionFvPatchScalarField::HeatFluxRecessionFvPatchScalarField
(
    const fvPatch& p,
    const DimensionedField<scalar, volMesh>& iF
)
  :
fixedValueFvPatchScalarField(p, iF),
debug_("no"),
mesh(patch().boundaryMesh().mesh()),
phaseName(word::null),
dictName(mesh.name()),
dict_(initDict()),
HeatFluxBoundaryConditions_
(
    mesh,
    phaseName,
    dictName,
    patch().index(),
    dict_
),
pyro_recessionBoundaryConditions_
(
    mesh,
    phaseName,
    dictName,
    patch().index(),
    dict_
)
{
  FatalErrorInFunction
      << "HeatFluxRecessionFvPatchScalarField(p,iF) not implemented."
      << exit(FatalError);
}


Foam::HeatFluxRecessionFvPatchScalarField::HeatFluxRecessionFvPatchScalarField
(
    const HeatFluxRecessionFvPatchScalarField& ptf,
    const fvPatch& p,
    const DimensionedField<scalar, volMesh>& iF,
    const fvPatchFieldMapper& mapper
)
  :
fixedValueFvPatchScalarField(ptf, p, iF, mapper),
debug_(ptf.debug_),
mesh(ptf.mesh),
phaseName(ptf.phaseName),
dictName(ptf.dictName),
dict_(ptf.dict_),
HeatFluxBoundaryConditions_
(
    mesh,
    phaseName,
    dictName,
    patch().index(),
    dict_
),
pyro_recessionBoundaryConditions_
(
    mesh,
    phaseName,
    dictName,
    patch().index(),
    dict_
)
{
}


Foam::HeatFluxRecessionFvPatchScalarField::HeatFluxRecessionFvPatchScalarField
(
    const fvPatch& p,
    const DimensionedField<scalar, volMesh>& iF,
    const dictionary& dict
)
  :
fixedValueFvPatchScalarField(p, iF, dict),
debug_(dict.lookupOrDefault<Switch>("debug","no")),
mesh(patch().boundaryMesh().mesh()),
phaseName(word::null),
dictName(mesh.name()),
dict_(dict),
HeatFluxBoundaryConditions_
(
    mesh,
    phaseName,
    dictName,
    patch().index(),
    dict_
),
pyro_recessionBoundaryConditions_
(
    mesh,
    phaseName,
    dictName,
    patch().index(),
    dict_
)
{
}


Foam::HeatFluxRecessionFvPatchScalarField::HeatFluxRecessionFvPatchScalarField
(
    const HeatFluxRecessionFvPatchScalarField& frpsf
)
  :
fixedValueFvPatchScalarField(frpsf),
debug_(frpsf.debug_),
mesh(frpsf.mesh),
phaseName(frpsf.phaseName),
dictName(frpsf.dictName),
dict_(frpsf.dict_),
HeatFluxBoundaryConditions_
(
    mesh,
    phaseName,
    dictName,
    patch().index(),
    dict_
),
pyro_recessionBoundaryConditions_
(
    mesh,
    phaseName,
    dictName,
    patch().index(),
    dict_
)
{
}


Foam::HeatFluxRecessionFvPatchScalarField::HeatFluxRecessionFvPatchScalarField
(
    const HeatFluxRecessionFvPatchScalarField& frpsf,
    const DimensionedField<scalar, volMesh>& iF
)
  :
fixedValueFvPatchScalarField(frpsf, iF),
debug_(frpsf.debug_),
mesh(frpsf.mesh),
phaseName(frpsf.phaseName),
dictName(frpsf.dictName),
dict_(frpsf.dict_),
HeatFluxBoundaryConditions_(frpsf.HeatFluxBoundaryConditions_),
pyro_recessionBoundaryConditions_(frpsf.pyro_recessionBoundaryConditions_)
{
}


// * * * * * * * * * * * * * * * Member Functions  * * * * * * * * * * * * * //

Foam::dictionary Foam::HeatFluxRecessionFvPatchScalarField::initDict()
{
  dictionary dict_;
  FatalError << "Not implemented" << exit(FatalError);
  return dict_;
}


void Foam::HeatFluxRecessionFvPatchScalarField::updateCoeffs()
{
  if (updated())
  {
    return;
  }

  if (debug_)
  {
    Info
        << "--- HeatFluxBoundaryConditions_.update(); --- "
        << "Foam::HeatFluxRecessionFvPatchScalarField::updateCoeffs()"
        << endl;
  }

  // Update the mapped heat flux and surface temperature first.
  HeatFluxBoundaryConditions_.update();

  if (debug_)
  {
    Info
        << "--- pyro_recessionBoundaryConditions_.update(); --- "
        << "Foam::HeatFluxRecessionFvPatchScalarField::updateCoeffs()"
        << endl;
  }

  // Then update the mapped recession rate and cellMotionU.
  pyro_recessionBoundaryConditions_.update();

  if (debug_)
  {
    Info
        << "--- fixedValueFvPatchScalarField::updateCoeffs(); --- "
        << "Foam::HeatFluxRecessionFvPatchScalarField::updateCoeffs()"
        << endl;
  }

  fixedValueFvPatchScalarField::updateCoeffs();

  if (debug_)
  {
    Info
        << "--- end --- "
        << "Foam::HeatFluxRecessionFvPatchScalarField::updateCoeffs()"
        << endl;
  }
}


void Foam::HeatFluxRecessionFvPatchScalarField::write(Ostream& os) const
{
  fvPatchScalarField::write(os);

  // Both helper objects use the same mapping dictionary.  Write it once
  // through HeatFlux to avoid duplicate mappingType/mappingFields entries.
  HeatFluxBoundaryConditions_.write(os);

  writeEntry(os, "value", *this);
}


// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

namespace Foam
{
makePatchTypeField
(
    fvPatchScalarField,
    HeatFluxRecessionFvPatchScalarField
);
}

// ************************************************************************* //
