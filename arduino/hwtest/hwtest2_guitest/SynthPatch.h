#ifndef SYNTHPATCH_H
#define SYNTHPATCH_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <typeinfo>

enum ParamType { Range,
                 Choice };

#define ParamRange(name, desc, val, ... /* min, max, fmt */) \
  Param(Range, name, desc, val, ##__VA_ARGS__)

#define ParamChoice(name, desc, val, choice_strs, num_choices) \
  Param(Choice, name, desc, val, 0, num_choices, "%s", choice_strs)

/*!
 *  @brief A Param is a value that can be set/get, with a range (if type Range) 
 *  or from a list of choices (if type Choice)
 */
class Param {
public:
  /*!
   *  @brief  Instantiate a Param from another Param
   *  @param  p a Param object
   */
  Param(Param* p) {
    type = p->type;
    name = p->name;
    desc = p->desc;
    val = p->val;
    minval = p->minval;
    maxval = p->maxval;
    fmt = p->fmt;
    choice_strs = p->choice_strs;
  }

  /*!
   *   @brief  Instantiates a Param object
   *   @param  aname
   *           name of this Param
   *   @param  aval
   *           the current value of this Param
   */
  Param(ParamType atype,
        const char* aname, const char* adesc, float aval, float aminval = 0, float amaxval = 255,
        const char* afmt = "%.0f", const char** achoice_strs = NULL) {
    type = atype;
    name = aname;
    desc = adesc;
    val = aval;
    minval = aminval;
    maxval = amaxval;
    fmt = afmt;
    choice_strs = achoice_strs;
  }

  // return the 0.0-1.0 "percentage" the val is in between minval and maxval
  float percent() {
    return (val - minval) / (maxval - minval);
  }

  // set val based on the "percentage" it should be between minval and maxval
  void set_percent(float pct) {
    val = pct * (maxval - minval) + minval;
  }
 
  // turn the Param's value into a string,
  void val_to_str(char* s, int slen) {
    if (choice_strs != NULL) {  // it's a ParamChoice
      snprintf(s, slen, "%s", choice_strs[(int)val]);
    } else {
      snprintf(s, slen, fmt, val);  // else ParamRange
    }
  }

  ParamType type;            // type of this param, Range or Choice
  const char* name;          // name of param
  const char* desc;
  float val;                 // value of param, even if a byte value from 0-255
  float minval;              // the minimum allowed value
  float maxval;              // maximum allowed value, or num_choices
  const char* fmt;           // how to format the value as a string
  const char** choice_strs;  // list of choices, if it's a ParamChoice
};


/*!
 *  @brief A Patch is a collection of Params with a name
 */
class Patch {
public:
  Patch(const char* aname, Param* aparams, int nparams) {
    strncpy(name, aname, 20);
    num_params = nparams;
    params = (Param*)malloc(sizeof(Param) * nparams);
    for (int i = 0; i < nparams; i++) {
      params[i] = Param(aparams[i]);
    }
  }
  char name[20];
  Param* params;
  int num_params;
};

#endif